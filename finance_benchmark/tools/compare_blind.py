#!/usr/bin/env python3
"""Compare les réponses en aveugle (analysis/blind/answers_v*.jsonl) aux brouillons (analysis/drafts/g*.jsonl).

Format d'une réponse en aveugle :
  {"id", "answer", "evidence": [{"document_id","page","text"}], "calculation": {"inputs","operation","result"}|null,
   "cannot_be_established": bool, "notes": "..."}

Signaux automatiques par question (la décision finale reste une adjudication humaine/agent sur les désaccords) :
  - négatif : le relecteur conclut-il aussi « cannot be established » ?
  - calcul  : résultat recalculé en aveugle ≈ résultat annoté (tolérance relative 1e-4) ?
  - evidence : au moins une page (document, page) en commun ?
  - nombres : chaque nombre de la réponse de référence apparaît-il dans la réponse en aveugle ?
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUM = re.compile(r"\d[\d,\. ]*\d|\d")


def load(pattern: str) -> dict[str, dict]:
    out = {}
    for f in sorted((ROOT / "analysis").glob(pattern)):
        for line in f.read_text("utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                out[d["id"]] = d
    return out


def numbers(text: str) -> set[str]:
    res = set()
    for m in NUM.findall(text):
        s = m.strip().rstrip(".,").replace(",", "").replace(" ", "")
        if s:
            res.add(s.rstrip("0").rstrip(".") if "." in s else s)
    return res


def compare(ref: dict, blind: dict | None) -> dict:
    if blind is None:
        return {"id": ref["id"], "auto_status": "missing", "issues": ["no blind answer"]}
    issues = []
    answerable = ref["metadata"].get("answerable", True)
    if blind.get("cannot_be_established") == answerable:
        issues.append("answerability disagrees" + (" (reviewer found an answer)" if not answerable else " (reviewer says cannot be established)"))
    if answerable:
        rc, bc = ref.get("calculation"), blind.get("calculation")
        if rc:
            if not bc or "result" not in bc:
                issues.append("no blind calculation")
            elif not math.isclose(float(bc["result"]), rc["result"], rel_tol=1e-4, abs_tol=1e-9):
                issues.append(f"calculation differs: blind {bc['result']} vs annotated {rc['result']}")
        rp = {(e["document_id"], e["page"]) for e in ref["evidence"]}
        bp = {(e.get("document_id"), e.get("page")) for e in blind.get("evidence", [])}
        if not rp & bp:
            issues.append(f"no common evidence page (annotated {sorted(rp)}, blind {sorted(bp)})")
        missing = sorted(n for n in numbers(ref["reference_answer"]) if n not in numbers(blind.get("answer", "")) and len(n) > 1)
        if missing:
            issues.append(f"numbers of the reference answer not in blind answer: {missing[:6]}")
    return {"id": ref["id"], "auto_status": "agree" if not issues else "check", "issues": issues}


def main() -> int:
    wave = sys.argv[1] if len(sys.argv) > 1 else "1"  # "1": g*.jsonl + answers_v*.jsonl ; "2": h*.jsonl + answers_w2v*.jsonl
    refs = load("drafts/g*.jsonl" if wave == "1" else "drafts/h*.jsonl")
    blinds = load("blind/answers_v*.jsonl" if wave == "1" else "blind/answers_w2v*.jsonl")
    rows = [compare(refs[i], blinds.get(i)) for i in sorted(refs)]
    (ROOT / "analysis" / "blind" / f"comparison_wave{wave}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), "utf-8")
    agree = sum(r["auto_status"] == "agree" for r in rows)
    print(f"{agree}/{len(rows)} agree automatically; {len(rows) - agree} to adjudicate")
    for r in rows:
        if r["auto_status"] != "agree":
            print(r["id"], r["auto_status"], "; ".join(r["issues"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
