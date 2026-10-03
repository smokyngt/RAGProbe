#!/usr/bin/env python3
"""Prépare la validation indépendante : extrait de chaque brouillon UNIQUEMENT {id, question}.

    python tools/make_blind_sets.py [--sets 4]     # analysis/drafts/g*.jsonl -> analysis/blind/v1.jsonl … vN.jsonl

Les questions sont mélangées de façon déterministe entre les lots : un relecteur ne reçoit ni la réponse de référence,
ni l'evidence, ni le groupe de l'annotateur. Il répond à partir des PDF seulement (voir tools/compare_blind.py).
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
    for f in sorted((ROOT / "analysis" / "drafts").glob(a.glob)):
        for line in f.read_text("utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                qs.append({"id": d["id"], "question": d["question"]})
    random.Random(2026).shuffle(qs)
    out = ROOT / "analysis" / "blind"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(a.sets):
        chunk = sorted(qs[i::a.sets], key=lambda q: q["id"])
        (out / f"{a.prefix}{i + 1}.jsonl").write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in chunk), "utf-8")
        print(f"{a.prefix}{i + 1}.jsonl: {len(chunk)} questions")


if __name__ == "__main__":
    main()
