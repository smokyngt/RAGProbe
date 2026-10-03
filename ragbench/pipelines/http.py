"""Adaptateur HTTP : POST JSON {"question": ...} -> {"answer": ..., "retrieved_chunks": [...]}.

`retrieved_chunks` : liste d'ids (str) ou d'objets {"chunk_id"|"id", "text"|"content", "score"}.
Fournir le texte permet au judge d'évaluer la groundedness.
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
            raise PipelineError(f"chunk sans identifiant : {item!r}")
        return RetrievedChunk(chunk_id=str(cid), text=item.get("text", item.get("content")),
                              score=item.get("score"))
    raise PipelineError(f"chunk de type inattendu : {type(item).__name__}")


class HTTPPipelineAdapter(PipelineAdapter):
    def __init__(self, cfg: PipelineConfig, session: requests.Session | None = None):
        self.cfg, self.name, self.version = cfg, cfg.name, cfg.version
        self.session = session or requests.Session()

    def query(self, question: str) -> PipelineResult:
        cfg, last = self.cfg, "aucune tentative"
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
            log.warning("tentative %d/%d échouée (%s)", attempt + 1, cfg.max_retries + 1, last)
        raise PipelineError(f"échec après {cfg.max_retries + 1} tentatives : {last}")

    def _parse(self, resp: requests.Response, latency_ms: float) -> PipelineResult:
        try:
            body = resp.json()
            answer = body[self.cfg.answer_field]
            chunks = body[self.cfg.chunks_field]
        except (ValueError, KeyError, TypeError) as e:
            raise PipelineError(f"réponse invalide ({type(e).__name__}: {e})") from e
        if not isinstance(answer, str) or not isinstance(chunks, list):
            raise PipelineError("`answer` doit être une chaîne et `retrieved_chunks` une liste")
        return PipelineResult(answer=answer, retrieved_chunks=[parse_chunk(c) for c in chunks],
                              latency_ms=latency_ms, raw=body)
