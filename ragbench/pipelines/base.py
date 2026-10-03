"""Le seul contrat entre le benchmark et une pipeline : `query(question) -> PipelineResult`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import PipelineResult


class PipelineError(Exception):
    """Échec de la pipeline (réseau, timeout, HTTP, payload invalide) — isolé par question."""


class PipelineAdapter(ABC):
    name: str = "pipeline"
    version: str = "unversioned"

    @abstractmethod
    def query(self, question: str) -> PipelineResult: ...
