"""Métriques de retrieval, calculées sur les `relevant_chunks` annotés.

Ajouter une métrique = écrire une fonction et l'enregistrer dans K_METRICS (@K) ou RANK_METRICS (sans K).
"""
from __future__ import annotations

import math
from typing import Callable, Sequence


KMetric = Callable[[Sequence[str], set[str], int], float]


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Part des passages pertinents présents dans le top-K."""
    return len(set(retrieved[:k]) & relevant) / len(relevant) if relevant else 0.0


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Part des K premiers résultats qui sont pertinents (dénominateur = K)."""
    return len(set(retrieved[:k]) & relevant) / k


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, c in enumerate(retrieved[:k], 1) if c in relevant)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    """1/rang du premier passage pertinent (0 s'il n'y en a pas)."""
    for rank, c in enumerate(retrieved, 1):
        if c in relevant:
            return 1 / rank
    return 0.0


K_METRICS: dict[str, KMetric] = {"recall": recall_at_k, "precision": precision_at_k, "ndcg": ndcg_at_k}
RANK_METRICS: dict[str, Callable[[Sequence[str], set[str]], float]] = {"mrr": reciprocal_rank}


def validate_metric_names(names: Sequence[str]) -> None:
    unknown = [n for n in names if n not in K_METRICS and n not in RANK_METRICS]
    if unknown:
        raise ValueError(f"métriques de retrieval inconnues {unknown} ; disponibles : "
                         f"{sorted(K_METRICS) + sorted(RANK_METRICS)}")


def dedupe(ids: Sequence[str]) -> list[str]:
    """Un chunk retourné deux fois ne doit compter qu'une fois (ordre conservé)."""
    return list(dict.fromkeys(ids))


def evaluate_retrieval(retrieved: Sequence[str], relevant: Sequence[str], ks: Sequence[int],
                       metrics: Sequence[str] = ("recall", "mrr")) -> dict[str, float]:
    """-> {"recall_at_1": ..., "recall_at_5": ..., "mrr": ...}"""
    ids, rel = dedupe(retrieved), set(relevant)
    out: dict[str, float] = {}
    for name in metrics:
        if name in K_METRICS:
            for k in ks:
                out[f"{name}_at_{k}"] = K_METRICS[name](ids, rel, k)
        else:
            out[name] = RANK_METRICS[name](ids, rel)
    return out
