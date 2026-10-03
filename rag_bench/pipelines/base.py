"""Contrat entre le benchmark et la pipeline testée.

Le benchmark ne fait PAS partie de la pipeline : il l'appelle via ce contrat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PipelineResult:
    answer: str
    retrieved_chunks: list[str]  # ids, ordre = classement du retriever
    meta: dict = field(default_factory=dict)  # latence, tokens, version, ...


class Pipeline(Protocol):
    name: str

    def run(self, question: str) -> PipelineResult: ...
