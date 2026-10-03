"""Adaptateur HTTP : POST {"question": ...} -> {"answer": ..., "retrieved_chunks": [...]}."""
from __future__ import annotations

import json
import urllib.request

from .base import PipelineResult


class HttpPipeline:
    def __init__(self, url: str, name: str = "http", timeout: float = 60.0, headers: dict | None = None):
        self.url, self.name, self.timeout = url, name, timeout
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def run(self, question: str) -> PipelineResult:
        req = urllib.request.Request(
            self.url, data=json.dumps({"question": question}).encode(), headers=self.headers
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.load(resp)
        return PipelineResult(
            answer=body["answer"],
            retrieved_chunks=list(body["retrieved_chunks"]),
            meta={k: v for k, v in body.items() if k not in ("answer", "retrieved_chunks")},
        )
