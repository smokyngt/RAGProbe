#!/usr/bin/env python3
"""Distribution report of the final dataset: types, styles, documents (primary and evidence), pages.

    python tools/report_stats.py        # -> datasets/finance_benchmark_v1_stats.json + printed summary
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ex = [json.loads(l) for l in (ROOT / "datasets" / "finance_benchmark_v1.jsonl").read_text("utf-8").splitlines() if l.strip()]
    man = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
    docs = {d["document_id"]: d for d in man["documents"]}
    primary = Counter(e["evidence"][0]["document_id"] if e["evidence"] else "(none: unanswerable)" for e in ex)
    ev_items = Counter(x["document_id"] for e in ex for x in e["evidence"])
    q_touch = Counter(d for e in ex for d in {x["document_id"] for x in e["evidence"]})
    stats = {
        "corpus": {"documents": man["n_documents"], "pages": man["total_pages"]},
        "questions": len(ex),
        "by_type": dict(Counter(e["metadata"]["type"] for e in ex).most_common()),
        "by_style": dict(Counter(e["metadata"].get("style", "lookup") for e in ex).most_common()),
        "by_difficulty": dict(Counter(e["metadata"]["difficulty"] for e in ex).most_common()),
        "flags": {"requires_calculation": sum(e["metadata"]["requires_calculation"] for e in ex),
                  "multi_document": sum(e["metadata"]["requires_multiple_documents"] for e in ex),
                  "unanswerable": sum(not e["metadata"]["answerable"] for e in ex)},
        "by_document": {d: {"company": docs[d]["company"], "title": docs[d]["title"], "type": docs[d]["document_type"], "pages": docs[d]["pages"],
                            "primary_questions": primary.get(d, 0), "questions_touching": q_touch.get(d, 0), "evidence_items": ev_items.get(d, 0)}
                        for d in docs},
        "failure_modes": dict(Counter(f for e in ex for f in e["metadata"].get("failure_modes", [])).most_common()),
    }
    (ROOT / "datasets" / "finance_benchmark_v1_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), "utf-8")
    print(f"corpus: {stats['corpus']['documents']} documents, {stats['corpus']['pages']} pages; questions: {stats['questions']}")
    print("types:", stats["by_type"]); print("styles:", stats["by_style"]); print("flags:", stats["flags"])
    print(f"{'document':<12}{'pages':>6}{'primary':>9}{'touching':>10}{'evidence':>10}  title")
    for d, v in stats["by_document"].items():
        print(f"{d:<12}{v['pages']:>6}{v['primary_questions']:>9}{v['questions_touching']:>10}{v['evidence_items']:>10}  {v['company']} — {v['title'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
