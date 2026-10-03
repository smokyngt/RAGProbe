"""Baseline de référence : BM25 + réponse extractive (meilleure phrase du top-1).

Sans LLM : sert à valider le benchmark et de plancher de comparaison.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..metrics import normalize_answer
from .base import PipelineResult


def _tokens(text: str) -> list[str]:
    return normalize_answer(text).split()


class BM25Pipeline:
    def __init__(self, corpus: dict[str, str], top_k: int = 10, k1: float = 1.5, b: float = 0.75):
        self.name = "bm25-extractive"
        self.corpus, self.top_k, self.k1, self.b = corpus, top_k, k1, b
        self.ids = list(corpus)
        self.docs = [Counter(_tokens(corpus[i])) for i in self.ids]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avgdl = sum(self.lens) / max(len(self.lens), 1)
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _score(self, q: list[str], i: int) -> float:
        d, dl, s = self.docs[i], self.lens[i], 0.0
        for t in q:
            f = d.get(t, 0)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def retrieve(self, question: str) -> list[str]:
        q = _tokens(question)
        scored = sorted(((self._score(q, i), self.ids[i]) for i in range(len(self.ids))), reverse=True)
        return [cid for s, cid in scored[: self.top_k] if s > 0]

    def run(self, question: str) -> PipelineResult:
        chunks = self.retrieve(question)
        answer = ""
        if chunks:
            q = set(_tokens(question))
            sents = [s for s in re.split(r"(?<=[.!?])\s+", self.corpus[chunks[0]]) if s]
            answer = max(sents, key=lambda s: len(q & set(_tokens(s))))
        return PipelineResult(answer=answer, retrieved_chunks=chunks)
