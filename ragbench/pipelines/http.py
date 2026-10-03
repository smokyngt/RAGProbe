"""Adaptateur HTTP : POST JSON {"question": ...} -> {"answer": ..., "retrieved_chunks": [...]}.

`retrieved_chunks`: list of ids (str) or objects {"chunk_id"|"id", "text"|"content", "score",
"document_id"|"doc_id"|"source", "page"|"page_number", "page_end"}. The text is needed by the judge (groundedness);
document_id + page let the benchmark match evidence annotated in the original documents (FinanceBench).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from ..config import PipelineConfig
from ..models import PipelineResult, RetrievedChunk
from .base import PipelineAdapter, PipelineError

log = logging.getLogger(__name__)
_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


def parse_chunk(item: Any) -> RetrievedChunk:
    if isinstance(item, str):
        return RetrievedChunk(chunk_id=item)
    if isinstance(item, dict):
        cid = item.get("chunk_id", item.get("id"))
        if cid is None:
            raise PipelineError(f"chunk without identifier: {item!r}")
        doc = item.get("document_id", item.get("doc_id", item.get("source")))
        try:
            page = item.get("page", item.get("page_number"))
            return RetrievedChunk(chunk_id=str(cid), text=item.get("text", item.get("content")), score=item.get("score"),
                                  document_id=str(doc) if doc is not None else None,
                                  page=int(page) if page is not None else None,
                                  page_end=int(item["page_end"]) if item.get("page_end") is not None else None)
        except (TypeError, ValueError) as e:  # e.g. a non-numeric score or page
            raise PipelineError(f"invalid chunk {item!r}: {e}") from e
    raise PipelineError(f"unexpected chunk type: {type(item).__name__}")


class HTTPPipelineAdapter(PipelineAdapter):
    def __init__(self, cfg: PipelineConfig, session: requests.Session | None = None):
        self.cfg, self.name, self.version = cfg, cfg.name, cfg.version
        self.session = session or requests.Session()

    def query(self, question: str) -> PipelineResult:
        cfg, last = self.cfg, "no attempt"
        for attempt in range(cfg.max_retries + 1):
            if attempt:
                time.sleep(cfg.retry_backoff_s * 2 ** (attempt - 1))
            t0 = time.perf_counter()
            try:
                resp = self.session.post(cfg.endpoint, json={cfg.request_field: question},
                                         headers=cfg.headers, timeout=cfg.timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                last = f"{type(e).__name__}: {e}"
            else:
                latency_ms = (time.perf_counter() - t0) * 1000
                if resp.status_code in _RETRY_STATUS:
                    last = f"HTTP {resp.status_code}"
                elif resp.status_code >= 400:  # erreur client : inutile de réessayer
                    raise PipelineError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                else:
                    return self._parse(resp, latency_ms)
            log.warning("attempt %d/%d failed (%s)", attempt + 1, cfg.max_retries + 1, last)
        raise PipelineError(f"failed after {cfg.max_retries + 1} attempts: {last}")

    def _parse(self, resp: requests.Response, latency_ms: float) -> PipelineResult:
        try:
            body = resp.json()
            answer = body[self.cfg.answer_field]
            chunks = body[self.cfg.chunks_field]
        except (ValueError, KeyError, TypeError) as e:
            raise PipelineError(f"invalid response ({type(e).__name__}: {e})") from e
        if not isinstance(answer, str) or not isinstance(chunks, list):
            raise PipelineError("`answer` must be a string and `retrieved_chunks` a list")
        return PipelineResult(answer=answer, retrieved_chunks=[parse_chunk(c) for c in chunks],
                              latency_ms=latency_ms, raw=body)
