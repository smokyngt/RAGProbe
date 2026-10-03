#!/usr/bin/env python3
"""Assemble annotation/merged_draft.jsonl from the annotation waves.

    python tools/build_draft.py

Sources: annotation/drafts/g*.jsonl (wave 1) + h*.jsonl (wave 2) + k*.jsonl (wave 3: documents added in v1.1) + m*.jsonl (wave 4: negatives, rebalancing); annotation/adjudication/adj*.json (verdicts):
  confirmed -> keep as is ; fix -> replace by the adjudicator's corrected example ; flag -> excluded.
annotation/retired.json ({id: reason}) retires questions on purpose (e.g. near-duplicates); ids are never reused.
annotation/enrichment/*.json ({id: {question_natural, key_facts}}) adds the natural phrasing and key facts.
annotation/repairs/sub*.jsonl replaces whole examples rewritten after the relevance review; they are re-verified like
any question (blind answers annotation/repairs/blind_answers*.jsonl, verdicts annotation/repairs/verdicts*.json: fix/flag).
Everything excluded is listed with its reason in datasets/excluded.json.
annotation/style_tags_wave1.json supplies `style` for wave-1 examples that predate the field.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text("utf-8").splitlines() if l.strip()]


def main() -> None:
    examples: dict[str, dict] = {}
    for pat in ("g*.jsonl", "h*.jsonl", "k*.jsonl", "m*.jsonl"):
        for f in sorted((ROOT / "annotation" / "drafts").glob(pat)):
            for ex in read_jsonl(f):
                examples[ex["id"]] = ex
    verdicts: dict[str, dict] = {}
    for f in sorted((ROOT / "annotation" / "adjudication").glob("adj*.json")):
        verdicts.update(json.loads(f.read_text("utf-8"))["decisions"])
    styles = json.loads((ROOT / "annotation" / "style_tags_wave1.json").read_text("utf-8"))
    excluded, fixed = [], []
    for qid, v in verdicts.items():
        if qid not in examples:
            continue
        if v["verdict"] == "fix" and v.get("example"):
            examples[qid] = v["example"]
            fixed.append(qid)
        elif v["verdict"] == "flag":
            excluded.append({"id": qid, "kind": "flagged_by_adjudication", "reasons": v["reasons"],
                             "question": examples.pop(qid)["question"]})
    retired_path = ROOT / "annotation" / "retired.json"
    for qid, reason in (json.loads(retired_path.read_text("utf-8")) if retired_path.exists() else {}).items():
        if qid in examples:
            excluded.append({"id": qid, "kind": "retired", "reasons": reason, "question": examples.pop(qid)["question"]})
    enriched = 0
    for f in sorted((ROOT / "annotation" / "enrichment").glob("*.json")):
        for qid, e in json.loads(f.read_text("utf-8")).items():
            if qid in examples:
                examples[qid]["question_natural"] = e["question_natural"]
                examples[qid]["key_facts"] = e.get("key_facts", [])
                enriched += 1
    for qid, ex in examples.items():
        ex["metadata"].setdefault("style", styles.get(qid, "lookup"))
        if qid in styles:  # wave-1 mapping is authoritative (adjudicated rewrites may have dropped the field)
            ex["metadata"]["style"] = styles[qid]
    repaired = []
    for f in sorted((ROOT / "annotation" / "repairs").glob("sub*.jsonl")):  # after enrichment: repairs carry their own
        for ex in read_jsonl(f):
            if ex["id"] in examples:
                examples[ex["id"]] = ex
                repaired.append(ex["id"])
    for f in sorted((ROOT / "annotation" / "repairs").glob("verdicts*.json")):
        for qid, v in json.loads(f.read_text("utf-8"))["decisions"].items():
            if qid not in examples:
                continue
            if v["verdict"] == "fix" and v.get("example"):
                examples[qid] = v["example"]
            elif v["verdict"] == "flag":
                excluded.append({"id": qid, "kind": "flagged_after_repair", "reasons": v["reasons"],
                                 "question": examples.pop(qid)["question"]})
    out = ROOT / "annotation" / "merged_draft.jsonl"
    out.write_text("".join(json.dumps(examples[i], ensure_ascii=False) + "\n" for i in sorted(examples)), "utf-8")
    (ROOT / "datasets" / "excluded.json").write_text(json.dumps(excluded, indent=2, ensure_ascii=False), "utf-8")
    print(f"{len(examples)} examples written ({len(fixed)} adjudicator fixes; {enriched} enriched; {len(repaired)} repaired; "
          f"{len(excluded)} excluded: {sorted(e['id'] for e in excluded)})")


if __name__ == "__main__":
    main()
