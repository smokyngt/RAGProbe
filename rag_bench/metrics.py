"""Métriques de retrieval (Recall@K, MRR, nDCG@K) et de QA (EM, F1)."""
from __future__ import annotations

import math
import re
import string
import unicodedata
from collections import Counter

# ---------- Retrieval ----------


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Part des passages pertinents présents dans le top-K."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & set(relevant)) / len(set(relevant))


def hit_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """1 si au moins un passage pertinent est dans le top-K."""
    return float(bool(set(retrieved[:k]) & set(relevant)))


def reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    rel = set(relevant)
    for i, c in enumerate(retrieved, start=1):
        if c in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    rel = set(relevant)
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(retrieved[:k], start=1) if c in rel)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0


# ---------- QA ----------

_ARTICLES = re.compile(r"\b(le|la|les|l|un|une|des|du|de|d|the|a|an)\b")


def normalize_answer(s: str) -> str:
    """Minuscules, sans accents, ponctuation ni articles (FR/EN)."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(" " if c in string.punctuation or c in "«»’" else c for c in s)
    s = _ARTICLES.sub(" ", s)
    return " ".join(s.split())


def exact_match(prediction: str, reference: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))


def f1_score(prediction: str, reference: str) -> float:
    p, r = normalize_answer(prediction).split(), normalize_answer(reference).split()
    if not p or not r:
        return float(p == r)
    common = sum((Counter(p) & Counter(r)).values())
    if common == 0:
        return 0.0
    prec, rec = common / len(p), common / len(r)
    return 2 * prec * rec / (prec + rec)
