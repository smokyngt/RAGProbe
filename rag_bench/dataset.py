"""Chargement du dataset : question -> réponse de référence + evidence (chunks)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Example:
    id: str
    question: str
    reference_answer: str
    relevant_chunks: list[str]
    tags: list[str] = field(default_factory=list)


def load_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_dataset(path: str | Path) -> list[Example]:
    examples = []
    for row in load_jsonl(path):
        examples.append(
            Example(
                id=row["id"],
                question=row["question"],
                reference_answer=row["reference_answer"],
                relevant_chunks=list(row["relevant_chunks"]),
                tags=list(row.get("tags", [])),
            )
        )
    ids = [e.id for e in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("ids de questions dupliqués dans le dataset")
    return examples


def load_corpus(path: str | Path) -> dict[str, str]:
    """corpus.jsonl : {"chunk_id": ..., "text": ...} -> {chunk_id: text}."""
    return {r["chunk_id"]: r["text"] for r in load_jsonl(path)}
