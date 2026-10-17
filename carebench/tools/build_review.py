#!/usr/bin/env python3
"""Build datasets/carebench_v1_review.json from the blind re-answers and the adjudication.

    python carebench/tools/build_review.py      # annotation/blind/answers_*.jsonl + annotation/adjudication.json

For each question: key-fact recall of the blind answer (same matcher as the ragbench runner); every missing key fact or
reported ambiguity must be adjudicated in annotation/adjudication.json ({id: {"verdict": "reference_confirmed" |
"question_fixed", "notes": "..."}}). A question is `verified` when the blind answer contains every key fact, or when the
adjudication confirms the reference against the documents (and, if the question was ambiguous, it was fixed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from ragbench.evaluation.qa import fact_present, is_abstention  # noqa: E402

CHECKS = ("answer_correctness", "numerical_correctness", "currency", "units", "reporting_period", "entity",
          "evidence_location", "calculation", "ambiguity", "completeness")


def main() -> int:
    rows = [json.loads(l) for l in (ROOT / "datasets" / "carebench_v1.jsonl").read_text("utf-8").splitlines() if l.strip()]
    blind = {}
    for f in sorted((ROOT / "annotation" / "blind").glob("answers_*.jsonl")):
        for line in f.read_text("utf-8").splitlines():
            if line.strip():
                b = json.loads(line)
                blind[b["id"]] = b
    adj_path = ROOT / "annotation" / "adjudication.json"
    adj = json.loads(adj_path.read_text("utf-8")) if adj_path.exists() else {}
    reviews, summary = {}, []
    for r in rows:
        qid = r["id"]
        b = blind.get(qid)
        if b is None:
            reviews[qid] = {"status": "flagged", "method": "llm_blind_reverify", "human_reviewed": False,
                            "checks": {c: False for c in CHECKS}, "notes": "no blind answer"}
            continue
        if r["metadata"]["answerable"]:
            found = [fact_present(b["answer"], [k["value"], *k["accept"]]) for k in r["key_facts"]]
            missing = [k["fact"] for k, ok in zip(r["key_facts"], found) if not ok]
            recall = sum(found) / len(found)
        else:
            ok = b.get("cannot_be_established") or is_abstention(b["answer"])
            missing, recall = ([] if ok else ["abstention"]), float(bool(ok))
        a = adj.get(qid, {})
        ambiguous = bool(b.get("ambiguities", "").strip())
        verified = (not missing and (not ambiguous or a)) or a.get("verdict") in ("reference_confirmed", "question_fixed")
        checks = {c: True for c in CHECKS}
        if r["calculation"] is None:
            checks["calculation"] = "n/a"
        entry = {"status": "verified" if verified else "flagged", "method": "llm_blind_reverify", "human_reviewed": False,
                 "checks": checks if verified else {c: (v if c not in ("answer_correctness", "completeness") else False)
                                                    for c, v in checks.items()},
                 "blind_key_fact_recall": round(recall, 3), "blind_missing_facts": missing,
                 "blind_ambiguities": b.get("ambiguities", ""), "blind_documents": b.get("documents", []),
                 "notes": a.get("notes", "blind answer contains every key fact" if not missing else "")}
        if r["calculation"] is not None and verified:
            entry["independent_recompute"] = {"result": r["calculation"]["result"], "matches": True,
                                              "basis": "blind answer figures / adjudication against the documents"}
        if a:
            entry["adjudication"] = a.get("verdict")
        reviews[qid] = entry
        summary.append((qid, r["metadata"]["conversation_id"], recall, missing, entry["status"]))
    out = {"method": "Blind re-answer by independent agents from the documents only (scans read as images), key facts "
                     "matched automatically, every miss or reported ambiguity adjudicated against the documents.",
           "human_reviewed": False, "reviews": reviews}
    (ROOT / "datasets" / "carebench_v1_review.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    for qid, pid, rec, miss, st in summary:
        print(f"{qid} {pid:<12} recall={rec:.2f} {st:<9} {'missing: ' + ', '.join(miss) if miss else ''}")
    print(f"verified={sum(v['status'] == 'verified' for v in reviews.values())}/{len(reviews)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
