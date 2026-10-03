#!/usr/bin/env python3
"""Pipeline RAG factice (BM25 + réponse extractive) exposée en HTTP, pour essayer le benchmark.

Volontairement SANS aucun import de `ragbench` : c'est une pipeline externe comme une autre.
    python examples/mock_pipeline.py --corpus datasets/sample_corpus.jsonl --port 8000 --top-k 5
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STOP = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "et", "est", "en", "quel", "quelle",
        "quels", "quelles", "que", "qui", "a", "au", "aux", "par", "pour", "dans", "sur", "il", "elle", "ce", "s"}


def tokens(text: str) -> list[str]:
    text = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in STOP]


class MockPipeline:
    def __init__(self, chunks: list[dict], top_k: int = 5):
        self.chunks, self.top_k = chunks, top_k
        self.tf = [Counter(tokens(c["text"])) for c in chunks]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df: Counter = Counter(w for t in self.tf for w in t)
        n = len(chunks)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def score(self, q: list[str], i: int) -> float:
        s = 0.0
        for w in q:
            f = self.tf[i].get(w, 0)
            if f:
                s += self.idf[w] * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.len[i] / self.avg))
        return s

    def query(self, question: str) -> dict:
        q = tokens(question)
        ranked = sorted(((self.score(q, i), i) for i in range(len(self.chunks))), reverse=True)
        top = [(s, self.chunks[i]) for s, i in ranked[: self.top_k] if s > 0]
        answer = ""
        if top:  # "génération" : la phrase du meilleur chunk qui partage le plus de mots avec la question
            sents = re.split(r"(?<=[.!?])\s+", top[0][1]["text"])
            answer = max(sents, key=lambda s: len(set(q) & set(tokens(s))))
        return {"answer": answer,
                "retrieved_chunks": [{"chunk_id": c["chunk_id"], "text": c["text"], "score": round(s, 4)} for s, c in top]}


def make_server(chunks: list[dict], host: str = "127.0.0.1", port: int = 0, top_k: int = 5) -> ThreadingHTTPServer:
    pipeline = MockPipeline(chunks, top_k)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                out, code = pipeline.query(body["question"]), 200
            except (ValueError, KeyError):
                out, code = {"error": "payload attendu : {\"question\": ...}"}, 400
            data = json.dumps(out, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="datasets/sample_corpus.jsonl")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()
    chunks = [json.loads(line) for line in open(args.corpus, encoding="utf-8") if line.strip()]
    srv = make_server(chunks, port=args.port, top_k=args.top_k)
    print(f"mock pipeline sur http://127.0.0.1:{args.port}/query (top_k={args.top_k})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
