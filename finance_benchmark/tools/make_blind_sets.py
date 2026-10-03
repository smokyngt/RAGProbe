#!/usr/bin/env python3
"""Prepare the independent validation: extract ONLY {id, question} from the drafts.

    python tools/make_blind_sets.py [--sets 4] [--glob 'h*.jsonl' --prefix w2v]
                                    # annotation/drafts/g*.jsonl -> annotation/blind/v1.jsonl … vN.jsonl

Questions are shuffled deterministically across sets: a reviewer never sees the reference answer, the evidence or the
annotator's group, and answers from the PDFs only (see tools/compare_blind.py).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", type=int, default=4)
    ap.add_argument("--glob", default="g*.jsonl", help="drafts to blind (wave 2: h*.jsonl)")
    ap.add_argument("--prefix", default="v", help="output prefix (wave 2: w2v -> w2v1.jsonl)")
    a = ap.parse_args()
    qs = []
    for f in sorted((ROOT / "annotation" / "drafts").glob(a.glob)):
        for line in f.read_text("utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                qs.append({"id": d["id"], "question": d["question"]})
    random.Random(2026).shuffle(qs)
    out = ROOT / "annotation" / "blind"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(a.sets):
        chunk = sorted(qs[i::a.sets], key=lambda q: q["id"])
        (out / f"{a.prefix}{i + 1}.jsonl").write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in chunk), "utf-8")
        print(f"{a.prefix}{i + 1}.jsonl: {len(chunk)} questions")


if __name__ == "__main__":
    main()
