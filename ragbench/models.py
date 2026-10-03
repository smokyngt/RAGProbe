"""Structures de données partagées (Pydantic). Aucune logique ici."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Sample(BaseModel):
    """Une ligne du dataset JSONL : question + vérité terrain."""

    id: str
    question: str
    reference_answer: str
    relevant_chunks: list[str] = Field(min_length=1)
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str | None = None  # nécessaire au judge (groundedness)
    score: float | None = None


class PipelineResult(BaseModel):
    answer: str
    retrieved_chunks: list[RetrievedChunk]  # ordre = classement du retriever
    latency_ms: float
    raw: dict[str, Any] | None = None


class JudgeScores(BaseModel):
    model_config = ConfigDict(extra="ignore")

    correctness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    groundedness: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class FailureType(str, Enum):
    SUCCESS = "SUCCESS"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"  # mauvaise réponse, preuves absentes du top-K
    GENERATION_FAILURE = "GENERATION_FAILURE"  # mauvaise réponse alors que les preuves étaient là
    GROUNDING_FAILURE = "GROUNDING_FAILURE"  # réponse correcte mais non soutenue par le contexte
    PIPELINE_ERROR = "PIPELINE_ERROR"  # erreur HTTP, timeout, réponse invalide


class TraceInput(BaseModel):
    question: str


class TraceGroundTruth(BaseModel):
    answer: str
    relevant_chunks: list[str]
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TracePipelineOutput(BaseModel):
    answer: str
    retrieved_chunks: list[RetrievedChunk]


class TraceAnalysis(BaseModel):
    """Les trois faits dont dérive le diagnostic (voir evaluation/diagnosis.py)."""

    retrieval_ok: bool  # toutes les preuves annotées sont dans le top-K max
    answer_correct: bool
    answer_correct_source: str  # "judge" | "token_f1"
    grounded: bool | None = None  # None si pas de judge


class Trace(BaseModel):
    """Trace complète d'une question : de quoi comprendre un échec a posteriori."""

    question_id: str
    input: TraceInput
    ground_truth: TraceGroundTruth
    pipeline_output: TracePipelineOutput | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    judge: JudgeScores | None = None
    judge_error: str | None = None
    analysis: TraceAnalysis | None = None
    diagnosis: FailureType
    latency_ms: float | None = None
    error: str | None = None


class RunMetadata(BaseModel):
    run_id: str
    timestamp: str
    pipeline: str
    pipeline_version: str
    dataset: str
    dataset_version: str
    dataset_sha256: str
    n_questions: int
    ragbench_version: str
    configuration: dict[str, Any]  # config complète, secrets masqués


class Summary(BaseModel):
    run: RunMetadata
    n_questions: int
    n_errors: int
    retrieval: dict[str, float]
    qa: dict[str, float]
    judge: dict[str, float] | None = None
    n_judged: int = 0
    latency_ms: dict[str, float] = Field(default_factory=dict)
    diagnosis: dict[str, int]
    # Réponse à la question centrale : pourquoi les réponses échouent-elles ?
    failure_analysis: dict[str, Any]
