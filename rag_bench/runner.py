"""Benchmark runner : boucle sur le dataset, appelle la pipeline, évalue, écrit results.json."""
from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from . import metrics as M
from .dataset import Example
from .judge import CRITERIA, LLMJudge
from .pipelines.base import Pipeline

KS = (1, 5, 10)
F1_OK = 0.5  # seuil de "réponse correcte" sans judge
JUDGE_OK = 0.5


def diagnose(retrieved: list[str], relevant: list[str], answer_ok: bool, k: int = max(KS)) -> str:
    """Localise l'origine d'un échec : retrieval, classement/contexte ou génération."""
    if answer_ok:
        return "ok"
    ranks = [retrieved.index(c) + 1 for c in relevant if c in retrieved[:k]]
    if not ranks:
        return "retrieval_miss"  # parsing / chunking / retriever
    if min(ranks) > 1:
        return "ranking_or_context"  # reranking / contexte noyé
    return "generation_error"  # le bon passage était 1er : le LLM a mal répondu


def evaluate_one(ex: Example, pipeline: Pipeline, corpus: dict[str, str] | None, judge: LLMJudge | None) -> dict:
    t0 = time.perf_counter()
    try:
        out = pipeline.run(ex.question)
    except Exception as e:  # une panne pipeline ne doit pas tuer le run
        return {"id": ex.id, "question": ex.question, "tags": ex.tags, "error": f"{type(e).__name__}: {e}",
                "diagnosis": "pipeline_error"}
    latency = time.perf_counter() - t0

    res: dict = {
        "id": ex.id, "question": ex.question, "tags": ex.tags,
        "reference_answer": ex.reference_answer, "answer": out.answer,
        "relevant_chunks": ex.relevant_chunks, "retrieved_chunks": out.retrieved_chunks,
        "latency_s": round(latency, 4), "meta": out.meta,
        "retrieval": {f"recall@{k}": M.recall_at_k(out.retrieved_chunks, ex.relevant_chunks, k) for k in KS}
        | {f"hit@{k}": M.hit_at_k(out.retrieved_chunks, ex.relevant_chunks, k) for k in KS}
        | {"mrr": M.reciprocal_rank(out.retrieved_chunks, ex.relevant_chunks),
           "ndcg@10": M.ndcg_at_k(out.retrieved_chunks, ex.relevant_chunks, 10)},
        "qa": {"em": M.exact_match(out.answer, ex.reference_answer),
               "f1": M.f1_score(out.answer, ex.reference_answer)},
    }
    answer_ok = res["qa"]["f1"] >= F1_OK
    if judge and corpus is not None:
        j = judge.evaluate(
            ex.question, ex.reference_answer, out.answer,
            [corpus[c] for c in ex.relevant_chunks if c in corpus],
            [corpus[c] for c in out.retrieved_chunks[:5] if c in corpus],
        )
        res["judge"] = j
        if "error" not in j:
            answer_ok = j["correctness"] >= JUDGE_OK
    res["diagnosis"] = diagnose(out.retrieved_chunks, ex.relevant_chunks, answer_ok)
    return res


def _mean(vals: list[float]) -> float:
    return round(statistics.fmean(vals), 4) if vals else 0.0


def aggregate(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    agg: dict = {"n": len(rows), "n_errors": len(rows) - len(ok)}
    if ok:
        agg["retrieval"] = {k: _mean([r["retrieval"][k] for r in ok]) for k in ok[0]["retrieval"]}
        agg["qa"] = {k: _mean([r["qa"][k] for r in ok]) for k in ok[0]["qa"]}
        agg["latency_s_mean"] = _mean([r["latency_s"] for r in ok])
        judged = [r["judge"] for r in ok if "judge" in r and "error" not in r["judge"]]
        if judged:
            agg["judge"] = {c: _mean([j[c] for j in judged]) for c in CRITERIA}
    diag: dict[str, int] = {}
    for r in rows:
        diag[r["diagnosis"]] = diag.get(r["diagnosis"], 0) + 1
    agg["diagnosis"] = diag
    return agg


def run_benchmark(examples: list[Example], pipeline: Pipeline, corpus=None, judge=None, out_path=None,
                  progress=None) -> dict:
    rows = []
    for i, ex in enumerate(examples, 1):
        rows.append(evaluate_one(ex, pipeline, corpus, judge))
        if progress:
            progress(i, len(examples), rows[-1])
    report = {
        "pipeline": getattr(pipeline, "name", type(pipeline).__name__),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {"ks": KS, "f1_threshold": F1_OK, "judge": judge is not None},
        "aggregate": aggregate(rows),
        "results": rows,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def compare(a: dict, b: dict) -> str:
    """Tableau de différences entre deux runs (a = baseline, b = candidat)."""
    lines = [f"{'metric':<22}{a['pipeline'][:18]:>20}{b['pipeline'][:18]:>20}{'delta':>10}"]
    for section in ("retrieval", "qa", "judge"):
        if section in a["aggregate"] and section in b["aggregate"]:
            for k, va in a["aggregate"][section].items():
                vb = b["aggregate"][section].get(k)
                if vb is not None:
                    lines.append(f"{section + '.' + k:<22}{va:>20.4f}{vb:>20.4f}{vb - va:>+10.4f}")
    return "\n".join(lines)
