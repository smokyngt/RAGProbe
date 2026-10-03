#!/usr/bin/env python3
"""Check one enrichment file without touching the shared dataset files (safe to run in parallel).

    python tools/check_enrichment.py annotation/enrichment/e1.json

An enrichment file maps question ids to {"question_natural": str, "key_facts": [{"fact", "value", "accept": [...]}]}.
Checks: ids exist in annotation/merged_draft.jsonl; schema; question_natural short and free of page/table references;
every key fact `value` is found in the verified reference answer (same matching rule as the ragbench runner);
no key facts for unanswerable questions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_dataset import Example, Report, check_enrichment  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(path: str) -> int:
    base = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "annotation" / "merged_draft.jsonl").read_text("utf-8").splitlines() if l.strip()}
    rep, n = Report(), 0
    for qid, e in json.loads(Path(path).read_text("utf-8")).items():
        if qid not in base:
            rep.err(qid, "unknown id")
            continue
        try:
            ex = Example.model_validate(base[qid] | {"question_natural": e.get("question_natural"), "key_facts": e.get("key_facts", [])})
        except Exception as err:  # noqa: BLE001
            rep.err(qid, str(err).replace("\n", " "))
            continue
        check_enrichment(ex, rep, required=True)
        n += 1
    for w in rep.warnings:
        print("WARN", w)
    for x in rep.errors:
        print("ERR ", x)
    print(f"{n} entries checked, errors={len(rep.errors)}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
