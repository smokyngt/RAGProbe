#!/usr/bin/env python3
"""Export the benchmark as plain question / answer / document rows, for an external runner.

    python tools/export_simple.py     # -> datasets/financebench_v1_simple.jsonl and .csv

Columns: id, question, question_natural, answer, documents (PDF file names in corpus/documents/, "|"-separated in the CSV),
pages ("fin_doc_011.pdf:162" per evidence item), answerable. Unanswerable questions have no document: the expected answer
says the information cannot be established from the corpus. The full annotation (evidence quotes, calculations, key facts,
metadata) stays in datasets/finance_benchmark_v1.jsonl.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    files = {d["document_id"]: d["filename"] for d in json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))["documents"]}
    rows = []
    for line in (ROOT / "datasets" / "finance_benchmark_v1.jsonl").read_text("utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        docs = list(dict.fromkeys(files[x["document_id"]] for x in e["evidence"]))
        rows.append({"id": e["id"], "question": e["question"], "question_natural": e.get("question_natural") or "",
                     "answer": e["reference_answer"], "documents": docs,
                     "pages": [f"{files[x['document_id']]}:{x['page']}" for x in e["evidence"]],
                     "answerable": e["metadata"]["answerable"]})
    out = ROOT / "datasets" / "financebench_v1_simple"
    out.with_suffix(".jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")
    with open(out.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r | {"documents": "|".join(r["documents"]), "pages": "|".join(r["pages"])})
    print(f"{len(rows)} rows -> {out.name}.jsonl / .csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
