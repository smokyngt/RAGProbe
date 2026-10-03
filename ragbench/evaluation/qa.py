"""Métriques QA déterministes : Exact Match et Token F1 (normalisation FR/EN)."""
from __future__ import annotations

import re
import string
import unicodedata
from collections import Counter

# Articles/déterminants courts. "a" est volontairement absent : c'est le verbe avoir en français.
_ARTICLES = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "the", "an"}  # + "an" (EN)
_PUNCT = set(string.punctuation) | set("«»’“”…–—")


def normalize(text: str) -> str:
    """Minuscules, sans accents, sans ponctuation, sans articles, espaces normalisés."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = "".join(" " if c in _PUNCT else c for c in text)
    return " ".join(t for t in text.split() if t not in _ARTICLES)


def exact_match(predicted: str, reference: str) -> float:
    return float(normalize(predicted) == normalize(reference))


def token_f1(predicted: str, reference: str) -> float:
    p, r = normalize(predicted).split(), normalize(reference).split()
    if not p or not r:
        return float(p == r)
    common = sum((Counter(p) & Counter(r)).values())
    if common == 0:
        return 0.0
    precision, recall = common / len(p), common / len(r)
    return 2 * precision * recall / (precision + recall)


def evaluate_answer(predicted: str, reference: str) -> dict[str, float]:
    return {"exact_match": exact_match(predicted, reference), "token_f1": token_f1(predicted, reference)}
