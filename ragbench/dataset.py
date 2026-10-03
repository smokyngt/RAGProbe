"""Chargement et validation du dataset JSONL."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .models import Sample


class DatasetError(Exception):
    pass


@dataclass
class Dataset:
    name: str
    version: str
    path: Path
    sha256: str  # empreinte du fichier : deux runs comparables ⇔ même hash
    samples: list[Sample]


def load_dataset(path: str | Path, name: str | None = None, version: str = "unversioned",
                 limit: int | None = None) -> Dataset:
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as e:
        raise DatasetError(f"unreadable dataset : {e}") from e
    samples: list[Sample] = []
    seen: set[str] = set()
    for lineno, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            sample = Sample.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as e:
            raise DatasetError(f"{path}:{lineno}: {e}") from e
        if sample.id in seen:
            raise DatasetError(f"{path}:{lineno}: duplicate id '{sample.id}'")
        seen.add(sample.id)
        samples.append(sample)
    if not samples:
        raise DatasetError(f"{path} : empty dataset")
    if limit is not None:
        samples = samples[:limit]
    return Dataset(name or path.stem, version, path, hashlib.sha256(data).hexdigest(), samples)
