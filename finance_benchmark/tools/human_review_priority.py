#!/usr/bin/env python3
"""Rank the questions that deserve a human reviewer first (explainable score, no model judgement).

    python tools/human_review_priority.py [--top 20]     # -> datasets/human_review_priority.json (+ printed table)

Risk features (additive):
  calculation +3 · superlative/ranking/count/list +3 (the extreme must be checked against every row) · multi-document +3 ·
  adjudicator had to REWRITE it (ambiguity existed) +3 · scope/basis words in the adjudication reason +2 ·
  unit_mismatch +2 · similar_table_labels/same_metric_multiple_years/footnote/header_dependency +1 each ·
  blind reviewer not 'high' confidence or voiced doubt +2 · automatic blind comparison disagreed +1 ·
  multi-page evidence +1 · ≥4 evidence items +1 · negative (verified by search only) +1 · yes_no/conditional +1.
Selection: highest score first, at most 5 questions per primary document so one report cannot fill the list.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_blind import compare, load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCOPE = re.compile(r"basis|scope|restat|CRR|special items|rounded|rounding|average|continuing|consolidated|standalone|total vs|before/after|definition", re.I)
DOUBT = re.compile(r"ambigu|two defensible|inconsisten|not comparable|mixed bas|misalign|unclear|cannot tell|rounding", re.I)
CHECK_HINT = {
    "calculation": "recompute from the figures printed on the cited page(s) and compare with the rounding stated in the answer",
    "extreme": "scan every candidate row/column in scope yourself; confirm no tie and that no row was omitted",
    "multi_doc": "open both documents; confirm period, entity and definition match across the two figures",
    "rewritten": "confirm the final wording leaves exactly one defensible answer",
    "scope": "check the stated basis (scope/period/definition) against the table header and footnotes",
    "units": "check currency, scale (thousand/million/billion) and percent vs percentage points",
    "similar": "check the value was read from the right row/column/year, not a look-alike elsewhere",
    "negative": "search the corpus again for synonyms to confirm the information really is absent",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--per-doc", type=int, default=5)
    a = ap.parse_args()
    ex = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "annotation" / "merged_draft.jsonl").read_text("utf-8").splitlines() if l.strip()}
    blinds = load("blind/answers_*.jsonl")
    adj: dict[str, dict] = {}
    for f in sorted((ROOT / "annotation" / "adjudication").glob("adj*.json")):
        adj.update(json.loads(f.read_text("utf-8"))["decisions"])
    rows = []
    for qid, e in ex.items():
        m, fm, score, why, hints = e["metadata"], set(e["metadata"].get("failure_modes", [])), 0, [], set()
        def add(n, reason, hint=None):
            nonlocal score
            score += n
            why.append(reason)
            if hint:
                hints.add(CHECK_HINT[hint])
        if e.get("calculation"): add(3, "calculation", "calculation")
        if m.get("style") in ("superlative", "ranking", "count", "list"): add(3, f"style={m['style']}", "extreme")
        if m.get("style") in ("yes_no", "conditional"): add(1, f"style={m['style']}")
        if m.get("requires_multiple_documents"): add(3, "multi-document", "multi_doc")
        v = adj.get(qid)
        if v and v["verdict"] == "fix": add(3, "rewritten by adjudicator (ambiguity existed)", "rewritten")
        if v and SCOPE.search(v.get("reasons", "")): add(2, "scope/basis issue discussed in adjudication", "scope")
        if "unit_mismatch" in fm: add(2, "unit_mismatch", "units")
        for f in ("similar_table_labels", "same_metric_multiple_years", "footnote", "header_dependency"):
            if f in fm: add(1, f, "similar" if "similar" in f or "same" in f else None)
        b = blinds.get(qid)
        if b and (b.get("confidence") != "high" or DOUBT.search(b.get("notes", ""))): add(2, "blind reviewer doubt/low confidence")
        if b and compare(e, b)["auto_status"] != "agree": add(1, "blind comparison disagreed")
        pages = {(x["document_id"], x["page"]) for x in e["evidence"]}
        if len(pages) >= 2: add(1, "multi-page evidence")
        if len(e["evidence"]) >= 4: add(1, "≥4 evidence items")
        if not m.get("answerable", True): add(1, "negative (verified by search only)", "negative")
        primary = e["evidence"][0]["document_id"] if e["evidence"] else "none"
        rows.append({"id": qid, "score": score, "primary_document": primary, "type": m["type"], "style": m.get("style"),
                     "why": why, "check": sorted(hints), "question": e["question"]})
    rows.sort(key=lambda r: (-r["score"], r["id"]))
    chosen, per = [], {}
    for r in rows:
        if per.get(r["primary_document"], 0) < a.per_doc:
            chosen.append(r)
            per[r["primary_document"]] = per.get(r["primary_document"], 0) + 1
        if len(chosen) == a.top:
            break
    out = {"method": "explainable additive risk score; see the docstring of tools/human_review_priority.py", "top": chosen}
    (ROOT / "datasets" / "human_review_priority.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    for i, r in enumerate(chosen, 1):
        print(f"{i:>2}. {r['id']} score={r['score']:<2} {r['primary_document']} {r['type']}/{r['style']}  {'; '.join(r['why'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
