"""Retrieval metrics, computed against the annotated ground truth.

Everything is computed on a single representation, `hits`: for each rank of the retrieved list, the set of
ground-truth items that the retrieved chunk covers.
  - `relevant_chunks` ground truth: a chunk covers the item with the same id;
  - `evidence` ground truth (document + page + text): a chunk covers an evidence item when it comes from the same
    document and its page range contains the evidence page, or when it contains most of the evidence text.

Adding a metric = one function on (hits, n_relevant[, k]) registered in K_METRICS (@K) or RANK_METRICS.
"""
from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Callable, Sequence

from ..models import EvidenceRef, RetrievedChunk
from .qa import normalize

Hits = Sequence[frozenset]
TEXT_OVERLAP_SAME_DOC = 0.6  # share of the evidence tokens that must appear in a chunk of the same document
TEXT_OVERLAP_ANY_DOC = 0.8  # stricter when the chunk carries no document id


# ---------- metrics on hits ----------

def _recall(hits: Hits, n_relevant: int, k: int) -> float:
    """Share of the relevant items covered by the top-K."""
    return len(frozenset().union(*hits[:k])) / n_relevant if n_relevant else 0.0


def _precision(hits: Hits, n_relevant: int, k: int) -> float:
    """Share of the K first results that cover at least one relevant item (denominator = K)."""
    return sum(1 for h in hits[:k] if h) / k


def _ndcg(hits: Hits, n_relevant: int, k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, h in enumerate(hits[:k], 1) if h)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(n_relevant, k) + 1))
    return dcg / ideal if ideal else 0.0


def _rr(hits: Hits, n_relevant: int) -> float:
    """1/rank of the first relevant result (0 if none)."""
    for rank, h in enumerate(hits, 1):
        if h:
            return 1 / rank
    return 0.0


K_METRICS: dict[str, Callable[[Hits, int, int], float]] = {"recall": _recall, "precision": _precision, "ndcg": _ndcg}
RANK_METRICS: dict[str, Callable[[Hits, int], float]] = {"mrr": _rr}


def validate_metric_names(names: Sequence[str]) -> None:
    unknown = [n for n in names if n not in K_METRICS and n not in RANK_METRICS]
    if unknown:
        raise ValueError(f"unknown retrieval metrics {unknown}; available: "
                         f"{sorted(K_METRICS) + sorted(RANK_METRICS)}")


def metrics_from_hits(hits: Hits, n_relevant: int, ks: Sequence[int],
                      metrics: Sequence[str] = ("recall", "mrr")) -> dict[str, float]:
    """-> {"recall_at_1": ..., "recall_at_5": ..., "mrr": ...}"""
    out: dict[str, float] = {}
    for name in metrics:
        if name in K_METRICS:
            for k in ks:
                out[f"{name}_at_{k}"] = K_METRICS[name](hits, n_relevant, k)
        else:
            out[name] = RANK_METRICS[name](hits, n_relevant)
    return out


# ---------- ground truth = chunk ids ----------

def dedupe(ids: Sequence[str]) -> list[str]:
    """A chunk returned twice only counts once (order kept)."""
    return list(dict.fromkeys(ids))


def chunk_hits(retrieved: Sequence[str], relevant: set[str]) -> list[frozenset]:
    return [frozenset({c}) & relevant for c in dedupe(retrieved)]


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    return _recall(chunk_hits(retrieved, relevant), len(relevant), k)


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    return _precision(chunk_hits(retrieved, relevant), len(relevant), k)


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    return _ndcg(chunk_hits(retrieved, relevant), len(relevant), k)


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    return _rr(chunk_hits(retrieved, relevant), len(relevant))


def evaluate_retrieval(retrieved: Sequence[str], relevant: Sequence[str], ks: Sequence[int],
                       metrics: Sequence[str] = ("recall", "mrr")) -> dict[str, float]:
    rel = set(relevant)
    return metrics_from_hits(chunk_hits(retrieved, rel), len(rel), ks, metrics)


# ---------- ground truth = evidence in the original documents ----------

def normalize_doc_id(doc_id: str | None) -> str | None:
    """'corpus/documents/fin_doc_011.pdf' and 'fin_doc_011' designate the same document."""
    if not doc_id:
        return None
    return PurePosixPath(doc_id.replace("\\", "/")).stem.lower()


def _tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if len(t) > 1 or t.isdigit()}


def text_overlap(evidence_text: str, chunk_text: str) -> float:
    """Share of the evidence tokens (words and numbers, '…' fragments included) found in the chunk."""
    ev = _tokens(re.sub(r"…|\[\.\.\.\]", " ", evidence_text))
    return len(ev & _tokens(chunk_text)) / len(ev) if ev else 0.0


def covers(chunk: RetrievedChunk, ev: EvidenceRef) -> bool:
    same_doc = normalize_doc_id(chunk.document_id) == normalize_doc_id(ev.document_id)
    if same_doc and chunk.page is not None and chunk.page <= ev.page <= (chunk.page_end or chunk.page):
        return True
    if chunk.text and ev.text:
        threshold = TEXT_OVERLAP_SAME_DOC if same_doc else (TEXT_OVERLAP_ANY_DOC if chunk.document_id is None else None)
        return threshold is not None and text_overlap(ev.text, chunk.text) >= threshold
    return False


def evidence_hits(retrieved: Sequence[RetrievedChunk], evidence: Sequence[EvidenceRef]) -> list[frozenset]:
    seen, unique = set(), []
    for c in retrieved:  # a chunk returned twice only counts once (first occurrence kept)
        if c.chunk_id not in seen:
            seen.add(c.chunk_id)
            unique.append(c)
    return [frozenset(i for i, ev in enumerate(evidence) if covers(c, ev)) for c in unique]
