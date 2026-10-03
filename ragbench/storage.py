"""Persistance d'un run : results/<run_id>/{summary.json, traces.jsonl}."""
from __future__ import annotations

import re
from pathlib import Path
from typing import IO

from .models import Summary, Trace


class RunNotFound(Exception):
    pass


def slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "-", text).strip("-")


def create_run_dir(results_dir: str | Path, base_id: str, explicit: bool) -> tuple[str, Path]:
    """run_id explicite : refuse d'écraser. run_id auto : suffixe _2, _3... en cas de collision."""
    root = Path(results_dir)
    run_id, n = base_id, 1
    while (root / run_id).exists():
        if explicit:
            raise FileExistsError(f"le run '{run_id}' existe déjà (choisir un autre --run-id)")
        n += 1
        run_id = f"{base_id}_{n}"
    path = root / run_id
    path.mkdir(parents=True)
    return run_id, path


class TraceWriter:
    """Écrit chaque trace dès qu'elle est prête : un crash ne perd pas les questions déjà évaluées."""

    def __init__(self, run_dir: Path):
        self._f: IO[str] = open(run_dir / "traces.jsonl", "w", encoding="utf-8")

    def write(self, trace: Trace) -> None:
        self._f.write(trace.model_dump_json() + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def write_summary(run_dir: Path, summary: Summary) -> None:
    (run_dir / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")


def _run_path(results_dir: str | Path, run_id: str) -> Path:
    path = Path(results_dir) / run_id
    if not path.is_dir():
        known = sorted(p.name for p in Path(results_dir).glob("*") if p.is_dir())
        raise RunNotFound(f"run '{run_id}' introuvable dans {results_dir} (existants : {known or 'aucun'})")
    return path


def load_summary(results_dir: str | Path, run_id: str) -> Summary:
    return Summary.model_validate_json((_run_path(results_dir, run_id) / "summary.json").read_text("utf-8"))


def load_traces(results_dir: str | Path, run_id: str) -> list[Trace]:
    text = (_run_path(results_dir, run_id) / "traces.jsonl").read_text("utf-8")
    return [Trace.model_validate_json(line) for line in text.splitlines() if line.strip()]
