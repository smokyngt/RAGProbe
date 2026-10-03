"""Structures de données partagées (Pydantic). Aucune logique ici."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceRef(BaseModel):
    """Ground truth tied to the ORIGINAL document (FinanceBench format), independent of any chunking."""

    document_id: str
    page: int = Field(ge=1)
    text: str | None = None


class Sample(BaseModel):
    """One JSONL line: question + ground truth.

    Two ground-truth formats are accepted:
      - `relevant_chunks`: ids of the pipeline's own chunks (simple, but tied to one chunking);
      - `evidence`: [{document_id, page, text}] in the original documents (FinanceBench) — a retrieved chunk
        counts as relevant when it comes from the same document and page, or contains most of the evidence text.
    An unanswerable question (`answerable: false`, also read from `metadata.answerable`) has no evidence:
    the expected behaviour is to say the information cannot be established.
    """

    id: str
    question: str
    reference_answer: str
    relevant_chunks: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    answerable: bool | None = None
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ground_truth(self):
        if self.answerable is None:
            self.answerable = bool(self.metadata.get("answerable", True))
        if self.answerable and not (self.relevant_chunks or self.evidence):
            raise ValueError("an answerable question needs `relevant_chunks` or `evidence`")
        return self


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str | None = None  # needed by the judge (groundedness) and by evidence matching
    score: float | None = None
    document_id: str | None = None  # provenance, needed to match `evidence` by page
    page: int | None = None  # first page of the chunk (1-based)
    page_end: int | None = None  # last page if the chunk spans several pages


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
    relevant_chunks: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    answerable: bool = True
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TracePipelineOutput(BaseModel):
    answer: str
    retrieved_chunks: list[RetrievedChunk]


class TraceAnalysis(BaseModel):
    """Les trois faits dont dérive le diagnostic (voir evaluation/diagnosis.py)."""

    retrieval_ok: bool | None  # all annotated evidence within the max top-K; None for unanswerable questions
    answer_correct: bool
    answer_correct_source: str  # "judge" | "token_f1" | "abstention_check"
    grounded: bool | None = None  # None si pas de judge


class Trace(BaseModel):
    """Trace complète d'une question : de quoi comprendre un échec a posteriori."""

    question_id: str
    input: TraceInput
    ground_truth: TraceGroundTruth
    pipeline_output: TracePipelineOutput | None = None
    metrics: dict[str, float] = Field(default_factory=dict)  # retrieval metrics absent for unanswerable questions
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
