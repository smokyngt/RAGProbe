#!/usr/bin/env python3
"""Texte par page (pdftotext -layout) pour aider l'annotation et vérifier les citations d'evidence.

    python tools/extract_pages.py                 # -> analysis/text/<document_id>.txt  (pages séparées par \\f)
    python tools/extract_pages.py --grep "operating income" [--doc fin_doc_001]
    python tools/extract_pages.py --doc fin_doc_001 --page 12            # print page 12 (1-based); --page 12-14 for a range

Ces fichiers sont dérivés (analysis/ est ignoré par git) et ne font pas partie du corpus gelé.
Une page vide dans un PDF qui n'est pas vide signale un scan : OCR nécessaire avant annotation.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pdf_page_texts(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    return pages[:-1] if pages and pages[-1] == "" else pages  # pdftotext termine chaque page par \f


def load_manifest(root: Path = ROOT) -> dict:
    return json.loads((root / "corpus" / "manifest.json").read_text("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep")
    ap.add_argument("--doc")
    ap.add_argument("--page", help="N or A-B (1-based, requires --doc)")
    a = ap.parse_args()
    out_dir = ROOT / "analysis" / "text"
    out_dir.mkdir(parents=True, exist_ok=True)
    for d in load_manifest()["documents"]:
        if a.doc and d["document_id"] != a.doc:
            continue
        target = out_dir / f"{d['document_id']}.txt"
        if not target.exists():
            target.write_text("\f".join(pdf_page_texts(ROOT / "corpus" / "documents" / d["filename"])), "utf-8")
        pages = target.read_text("utf-8").split("\f")
        empty = sum(not p.strip() for p in pages)
        if empty > len(pages) * 0.5:
            print(f"⚠ {d['document_id']} : {empty}/{len(pages)} pages sans texte (scan ? OCR requis)", file=sys.stderr)
        if a.page:
            lo, _, hi = a.page.partition("-")
            for n in range(int(lo), int(hi or lo) + 1):
                print(f"===== {d['document_id']} PAGE {n} / {len(pages)} =====")
                print(pages[n - 1].rstrip())
        if a.grep:
            rx = re.compile(a.grep, re.I)
            for n, text in enumerate(pages, 1):
                for line in text.splitlines():
                    if rx.search(line):
                        print(f"{d['document_id']} p.{n}: {line.strip()[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
