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


def fact_normalize(text: str) -> str:
    """Normalisation for key-fact matching: keeps numbers intact but makes their formatting irrelevant.

    '€ 1,540 million' -> '€1540 million' ; '29.4 %' -> '29.4%' ; '−1 494' -> '-1494' ; "CHF 1'234.5" -> 'chf 1234.5'.
    """
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"[\u2010-\u2015\u2212]", "-", t)  # dashes / unicode minus
    t = re.sub(r"(?<=\d)[\s'’](?=\d{3}\b)", "", t)  # thousands separators: space, thin space, apostrophe
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)  # thousands separators: comma
    t = re.sub(r"\s+%", "%", t)
    t = re.sub(r"([€$£])\s+", r"\1", t)
    return " ".join(t.split())


def fact_present(answer: str, accept: list[str]) -> bool:
    """True if one accepted formulation appears in the answer (a number never matches inside a longer number)."""
    a = fact_normalize(answer)
    for v in accept:
        v = fact_normalize(v).rstrip(".")
        if not v:
            continue
        pattern = (r"(?<![\d.])" if v[0].isdigit() else "") + re.escape(v) + (r"(?![\d])" if v[-1].isdigit() else "")
        if re.search(pattern, a):
            return True
    return False


def key_fact_scores(predicted: str, key_facts: list) -> dict[str, float]:
    """Share of the key facts present in the answer, and whether all of them are (deterministic scoring)."""
    found = [fact_present(predicted, [f.value, *f.accept]) for f in key_facts]
    return {"key_fact_recall": sum(found) / len(found), "key_facts_all": float(all(found))}


def evaluate_answer(predicted: str, reference: str, key_facts: list | None = None) -> dict[str, float]:
    out = {"exact_match": exact_match(predicted, reference), "token_f1": token_f1(predicted, reference)}
    if key_facts:
        out |= key_fact_scores(predicted, key_facts)
    return out


_ABSTENTION = re.compile(
    r"cannot be (established|determined|found|answered|derived|confirmed)|can ?not (determine|find|answer)|"
    r"(is|are) not (provided|disclosed|available|reported|stated|mentioned|included)|no (information|data|figure)|"
    r"insufficient (information|evidence)|unable to (find|determine|answer)|does not (contain|provide|disclose|mention|report)|"
    r"not possible to (determine|establish)|ne (peut|permet) pas|aucune (information|donnée)|n'est pas (disponible|fourni|indiqué)",
    re.I)


def is_abstention(answer: str) -> bool:
    """True when the answer says the information cannot be established (expected for unanswerable questions)."""
    return bool(_ABSTENTION.search(answer or ""))
