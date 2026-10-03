"""Benchmark dorking : chaque tâche = objectif + contraintes attendues + URLs de référence.

Statuts alignés sur le rapport Prosperify : pass / partial / fail / app_error.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from . import dorks
from . import metrics as M
from .dataset import load_jsonl
from .dork_gen import DorkGenerator


def load_pages(path) -> list[dorks.Page]:
    return [dorks.Page(r["url"], r["title"], r["text"]) for r in load_jsonl(path)]


def constraint_score(d: dorks.Dork, exp: dict) -> tuple[float, dict]:
    """Part des contraintes attendues satisfaites par la requête (site, filetype, phrases, exclusions)."""
    checks: dict[str, bool] = {}
    if exp.get("site"):
        checks["site"] = d.has("site", exp["site"])
    if exp.get("filetype"):
        checks["filetype"] = d.has("filetype", exp["filetype"]) or d.has("ext", exp["filetype"])
    for p in exp.get("phrases", []):
        checks[f'phrase:{p}'] = any(c.value.lower() == p.lower() and not c.negated for c in d.clauses)
    for x in exp.get("exclude", []):
        checks[f"exclude:{x}"] = any(c.value.lower() == x.lower() and c.negated for c in d.clauses)
    return (sum(checks.values()) / len(checks) if checks else 1.0), checks


def evaluate_task(task: dict, gen: DorkGenerator, engine: dorks.SimulatedEngine, k: int = 10) -> dict:
    row = {"id": task["id"], "goal": task["goal"], "gold_urls": task["gold_urls"]}
    try:
        query = gen.generate(task["goal"])
        d = dorks.parse(query)
        urls = engine.search(query, k)
    except Exception as e:
        return row | {"status": "app_error", "error": f"{type(e).__name__}: {e}"}
    cscore, checks = constraint_score(d, task.get("expected", {}))
    rec5 = M.recall_at_k(urls, task["gold_urls"], 5)
    # précision@5 : pénalise les requêtes trop larges qui noient la cible
    prec5 = (len(set(urls[:5]) & set(task["gold_urls"])) / len(urls[:5])) if urls else 0.0
    if not d.valid:
        status = "fail"
    elif cscore == 1.0 and rec5 == 1.0 and prec5 >= 0.5:
        status = "pass"
    elif rec5 > 0 or cscore >= 0.5:
        status = "partial"
    else:
        status = "fail"
    return row | {
        "query": query, "syntax_valid": d.valid, "syntax_errors": d.errors,
        "constraints": checks, "constraint_score": round(cscore, 4),
        "results": urls, "recall@5": rec5, "precision@5": round(prec5, 4),
        "mrr": M.reciprocal_rank(urls, task["gold_urls"]), "status": status,
    }


def run_dork_benchmark(tasks, gen, engine, out_path=None) -> dict:
    rows = [evaluate_task(t, gen, engine) for t in tasks]
    ok = [r for r in rows if r["status"] != "app_error"]
    mean = lambda key: round(statistics.fmean(r[key] for r in ok), 4) if ok else 0.0
    status = {s: sum(r["status"] == s for r in rows) for s in ("pass", "partial", "fail", "app_error")}
    report = {
        "track": "dorking", "pipeline": gen.name,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "aggregate": {
            "n": len(rows), "status": status,
            "syntax_valid": round(sum(r["syntax_valid"] for r in ok) / len(ok), 4) if ok else 0.0,
            "constraint_score": mean("constraint_score"), "recall@5": mean("recall@5"),
            "precision@5": mean("precision@5"), "mrr": mean("mrr"),
        },
        "results": rows,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
