#!/usr/bin/env python3
"""Aggregate the relevance (pertinence) review of every question.

    python tools/relevance_report.py        # annotation/relevance/*.json -> datasets/relevance_report.json (+ printed summary)

Each reviewer file maps a question id to:
  {"user_realism": 1-5,          would a real analyst / investor / auditor / risk or compliance officer ask this?
   "decision_value": 1-5,        does the answer matter for an analysis, a decision or a control (vs trivia)?
   "financial_depth": 1-5,       does it need financial understanding (units, bases, definitions, statements)?
   "benchmark_value": 1-5,       does it test a meaningful RAG ability (retrieval trap, multi-hop, calculation, abstention)?
   "clarity": 1-5,               one defensible answer, well scoped
   "natural_ok": bool, "key_facts_ok": bool,       is the natural variant faithful and unambiguous; are the key facts right and complete?
   "redundant_with": [ids], "recommendation": "keep" | "rewrite" | "drop", "note": "…"}
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIMS = ("user_realism", "decision_value", "financial_depth", "benchmark_value", "clarity")


def main() -> int:
    ex = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "annotation" / "merged_draft.jsonl").read_text("utf-8").splitlines() if l.strip()}
    rev: dict[str, dict] = {}
    for f in sorted((ROOT / "annotation" / "relevance").glob("*.json")):
        rev.update(json.loads(f.read_text("utf-8")))
    missing = sorted(set(ex) - set(rev))
    rows = {q: r for q, r in rev.items() if q in ex}
    mean = lambda xs: round(statistics.fmean(xs), 2) if xs else None
    overall = {d: mean([r[d] for r in rows.values()]) for d in DIMS}
    score = {q: round(statistics.fmean(r[d] for d in DIMS), 2) for q, r in rows.items()}
    by = lambda key: {k: mean([score[q] for q in qs]) for k, qs in sorted(_group(rows, ex, key).items())}
    report = {
        "n_reviewed": len(rows), "missing": missing, "dimensions": overall,
        "mean_score": mean(list(score.values())),
        "recommendations": dict(Counter(r["recommendation"] for r in rows.values())),
        "natural_ok": sum(bool(r.get("natural_ok")) for r in rows.values()),
        "key_facts_ok": sum(bool(r.get("key_facts_ok")) for r in rows.values()),
        "by_type": by("type"), "by_style": by("style"), "by_document": by("document"),
        "lowest": sorted(({"id": q, "score": score[q], "recommendation": rows[q]["recommendation"], "note": rows[q].get("note", "")}
                          for q in rows), key=lambda r: (r["score"], r["id"]))[:15],
        "to_act_on": [{"id": q, "recommendation": r["recommendation"], "natural_ok": r.get("natural_ok"),
                       "key_facts_ok": r.get("key_facts_ok"), "note": r.get("note", "")}
                      for q, r in sorted(rows.items())
                      if r["recommendation"] != "keep" or not r.get("natural_ok") or not r.get("key_facts_ok")],
        "per_question": {q: {**{d: rows[q][d] for d in DIMS}, "score": score[q], "recommendation": rows[q]["recommendation"]}
                         for q in sorted(rows)},
    }
    (ROOT / "datasets" / "relevance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    print(f"reviewed {len(rows)}/{len(ex)}; mean score {report['mean_score']}; dimensions {overall}")
    print("recommendations:", report["recommendations"], "| natural ok:", report["natural_ok"], "| key facts ok:", report["key_facts_ok"])
    for r in report["to_act_on"]:
        print(f"  {r['id']} {r['recommendation']:<8} natural_ok={r['natural_ok']} key_facts_ok={r['key_facts_ok']}  {r['note'][:150]}")
    return 0


def _group(rows: dict, ex: dict, key: str) -> dict[str, list[str]]:
    g: dict[str, list[str]] = defaultdict(list)
    for q in rows:
        m = ex[q]["metadata"]
        k = m.get(key) if key != "document" else (ex[q]["evidence"][0]["document_id"] if ex[q]["evidence"] else "(unanswerable)")
        g[k or "?"].append(q)
    return g


if __name__ == "__main__":
    sys.exit(main())
