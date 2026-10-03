"""Configuration YAML validée. Les `${VAR}` sont résolues depuis l'environnement (pas de secret en dur)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigError(Exception):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # une faute de frappe dans le YAML doit se voir


class PipelineConfig(_Strict):
    name: str
    version: str = "unversioned"
    endpoint: str
    timeout: float = Field(30.0, gt=0)
    max_retries: int = Field(2, ge=0, le=5)
    retry_backoff_s: float = Field(1.0, ge=0)
    headers: dict[str, str] = Field(default_factory=dict)
    request_field: str = "question"
    answer_field: str = "answer"
    chunks_field: str = "retrieved_chunks"


class DatasetConfig(_Strict):
    name: str | None = None  # défaut : nom du fichier
    version: str = "unversioned"


class BenchmarkConfig(_Strict):
    top_k: list[int] = [1, 5, 10]
    retrieval_metrics: list[str] = ["recall", "mrr"]  # + "precision", "ndcg" disponibles
    question_field: Literal["question", "question_natural"] = "question"  # natural = short user-like phrasing
    answer_correct_f1_threshold: float = Field(0.5, ge=0, le=1)  # without judge and without key facts
    judge_correct_threshold: float = Field(0.5, ge=0, le=1)
    grounded_threshold: float = Field(0.5, ge=0, le=1)

    @field_validator("top_k")
    @classmethod
    def _top_k(cls, v: list[int]) -> list[int]:
        if not v or any(k < 1 for k in v):
            raise ValueError("top_k doit contenir des entiers >= 1")
        return sorted(set(v))

    @field_validator("retrieval_metrics")
    @classmethod
    def _metrics(cls, v: list[str]) -> list[str]:
        from .evaluation.retrieval import validate_metric_names

        validate_metric_names(v)
        return v


class JudgeConfig(_Strict):
    enabled: bool = False
    provider: Literal["anthropic", "openai_compatible"] = "anthropic"
    model: str = "claude-opus-5-5"
    max_tokens: int = Field(4096, ge=256)  # la réflexion du modèle compte dans max_tokens
    max_evidence_chunks: int = Field(5, ge=1)
    base_url: str | None = None  # openai_compatible uniquement
    api_key_env: str | None = None  # nom de la variable d'env contenant la clé
    temperature: float | None = None  # ignoré par anthropic (non supporté par certains modèles)


class Config(_Strict):
    pipeline: PipelineConfig
    dataset: DatasetConfig = DatasetConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()
    judge: JudgeConfig = JudgeConfig()

    def redacted(self) -> dict[str, Any]:
        """Version sauvegardée dans summary.json : valeurs des headers masquées."""
        d = self.model_dump(mode="json")
        d["pipeline"]["headers"] = {k: "***" for k in d["pipeline"]["headers"]}
        return d


_VAR = re.compile(r"\$\{(\w+)\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        def sub(m: re.Match) -> str:
            if m.group(1) not in os.environ:
                raise ConfigError(f"environment variable not set: {m.group(1)}")
            return os.environ[m.group(1)]
        return _VAR.sub(sub, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load_config(path: str | Path) -> Config:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"unreadable configuration ({path}): {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} : a YAML mapping is expected")
    try:
        return Config.model_validate(_expand(raw))
    except ValueError as e:  # pydantic.ValidationError hérite de ValueError
        raise ConfigError(f"invalid configuration ({path}):\n{e}") from e
