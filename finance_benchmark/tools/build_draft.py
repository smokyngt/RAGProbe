#!/usr/bin/env python3
"""Assemble annotation/merged_draft.jsonl from the annotation waves.

    python tools/build_draft.py

Sources: annotation/drafts/g*.jsonl (wave 1) + h*.jsonl (wave 2) + k*.jsonl (wave 3: documents added in v1.1); annotation/adjudication/adj*.json (verdicts):
  confirmed -> keep as is ; fix -> replace by the adjudicator's corrected example ; flag -> excluded (listed in datasets/excluded_flagged.json).
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
    for pat in ("g*.jsonl", "h*.jsonl", "k*.jsonl"):
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
            excluded.append({"id": qid, "reasons": v["reasons"], "question": examples.pop(qid)["question"]})
    for qid, ex in examples.items():
        ex["metadata"].setdefault("style", styles.get(qid, "lookup"))
        if qid in styles:  # wave-1 mapping is authoritative (adjudicated rewrites may have dropped the field)
            ex["metadata"]["style"] = styles[qid]
    out = ROOT / "annotation" / "merged_draft.jsonl"
    out.write_text("".join(json.dumps(examples[i], ensure_ascii=False) + "\n" for i in sorted(examples)), "utf-8")
    (ROOT / "datasets" / "excluded_flagged.json").write_text(json.dumps(excluded, indent=2, ensure_ascii=False), "utf-8")
    print(f"{len(examples)} examples written ({len(fixed)} adjudicator fixes applied: {sorted(fixed)}; {len(excluded)} excluded as flagged)")


if __name__ == "__main__":
    main()
