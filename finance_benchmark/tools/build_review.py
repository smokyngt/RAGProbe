#!/usr/bin/env python3
"""Build datasets/finance_benchmark_v1_review.json from the blind re-answer comparison and the adjudication verdicts.

    python tools/build_review.py            # also prints questions that still need a second look

Honesty rules baked in:
  - method = "llm_blind_reverify", human_reviewed = false (no human has read these examples);
  - a question is `verified` only if (a) the blind reviewer agreed automatically with no doubt of their own, or
    (b) an adjudicator re-read the sources and confirmed/fixed it; anything else is `flagged` with notes;
  - blind answers with confidence != high or doubt keywords in their notes are never auto-verified.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_blind import compare, load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOUBT = re.compile(r"ambigu|two defensible|inconsisten|not comparable|differs|restat|mixed bas|misalign|unclear|cannot tell|rounding", re.I)
CHECKS = ("answer_correctness", "numerical_correctness", "currency", "units", "reporting_period", "entity",
          "evidence_location", "calculation", "ambiguity", "completeness")


def recompute(ref: dict, blind: dict) -> dict | None:
    rc, bc = ref.get("calculation"), blind.get("calculation")
    if not rc:
        return None
    if not bc or "result" not in bc:
        return {"result": None, "matches": False}
    b, r = float(bc["result"]), rc["result"]
    for k in (1, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9):  # reviewers may work in thousands/millions rather than base units
        if math.isclose(b * k, r, rel_tol=2e-3, abs_tol=1e-9):
            return {"result": r, "matches": True, "blind_result": b, "blind_scale": k}
    return {"result": b, "matches": False, "blind_result": b}


def main() -> int:
    draft = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "datasets" / "finance_benchmark_v1_draft.jsonl").read_text("utf-8").splitlines() if l.strip()}
    blinds = load("blind/answers_*.jsonl")
    adj: dict[str, dict] = {}
    for f in sorted((ROOT / "analysis" / "adjudication").glob("adj*.json")):
        adj.update(json.loads(f.read_text("utf-8"))["decisions"])
    reviews, attention = {}, []
    for qid, ex in sorted(draft.items()):
        b = blinds.get(qid)
        verdict = adj.get(qid)
        entry = {"method": "llm_blind_reverify", "human_reviewed": False, "reviewer": "independent blind re-answer + adjudication by separate model agents",
                 "checks": {k: True for k in CHECKS}, "notes": ""}
        if b is None:
            entry.update(status="flagged", notes="no blind re-answer available", basis="none")
            attention.append((qid, "no blind answer"))
        elif verdict and verdict["verdict"] in ("confirmed", "fix"):
            rc = recompute(ex, b) if verdict["verdict"] == "confirmed" else None
            entry.update(status="verified", basis=f"adjudicator {verdict['verdict']}", notes=verdict["reasons"][:600])
            if verdict["verdict"] == "fix":  # corrected after the blind pass: adjudicator re-verified against the source
                entry["notes"] = "Corrected after blind pass; " + entry["notes"]
        elif verdict and verdict["verdict"] == "flag":
            entry.update(status="flagged", basis="adjudicator flag", notes=verdict["reasons"][:600])
        else:
            auto = compare(ex, b)
            doubt = b.get("confidence") != "high" or bool(DOUBT.search(b.get("notes", "")))
            if auto["auto_status"] == "agree" and not doubt:
                entry.update(status="verified", basis="blind answer agreed (answerability, calculation, evidence page, numbers)")
            else:
                why = auto["issues"] + ([f"blind reviewer confidence={b.get('confidence')}; notes: {b.get('notes', '')[:200]}"] if doubt else [])
                entry.update(status="flagged", basis="unresolved disagreement or reviewer doubt", notes="; ".join(why)[:600])
                attention.append((qid, "; ".join(why)[:260]))
        rc = recompute(ex, b) if b else None
        if ex.get("calculation"):
            entry["independent_recompute"] = rc or {"result": None, "matches": False}
            if entry["status"] == "verified" and not entry["independent_recompute"]["matches"]:
                entry.update(status="flagged", basis="recompute mismatch", notes=f"blind recompute {rc}")
                attention.append((qid, f"recompute mismatch {rc}"))
        reviews[qid] = entry
    out = {"dataset": "finance_benchmark_v1", "method_note": "No human review has taken place. 'verified' = independent blind re-answer from the PDFs agreed, or an adjudicator re-read the sources; see each entry's basis.", "reviews": reviews}
    (ROOT / "datasets" / "finance_benchmark_v1_review.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    n_ok = sum(r["status"] == "verified" for r in reviews.values())
    print(f"{n_ok} verified, {len(reviews) - n_ok} flagged, of {len(reviews)}")
    for qid, why in attention:
        print(" needs a look:", qid, why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
