#!/usr/bin/env python3
"""Télécharge les documents sélectionnés (corpus/candidates.json -> selected:true) et construit le manifest.

    python tools/fetch_corpus.py            # télécharge + écrit corpus/manifest.json et corpus/fetch_report.json
    python tools/fetch_corpus.py --freeze   # vérifie les SHA-256, écrit corpus/FROZEN.json, passe les fichiers en lecture seule

Provenance conservée par document : source_url, domaine, date de récupération, SHA-256, taille, pages (pdfinfo).
Un échec (HTTP, pas un PDF, trop gros) est consigné dans fetch_report.json, jamais masqué.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
DOCS = CORPUS / "documents"
UA = "FinanceBench-corpus-builder/1.0 (research; public documents only)"
MAX_BYTES = 250 * 1024 * 1024


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pdf_pages(p: Path) -> int:
    out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, check=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise ValueError("pdfinfo: nombre de pages introuvable")
    return int(m.group(1))


def download(url: str, dest: Path) -> tuple[str, int]:
    tmp = dest.with_suffix(".part")
    with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
        r.raise_for_status()
        ctype, size = r.headers.get("Content-Type", ""), 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError(f"fichier > {MAX_BYTES >> 20} Mo")
                f.write(chunk)
    with open(tmp, "rb") as f:
        if f.read(5) != b"%PDF-":
            tmp.unlink()
            raise ValueError(f"pas un PDF (Content-Type: {ctype})")
    tmp.replace(dest)
    return ctype, size


def build(args) -> int:
    if (CORPUS / "FROZEN.json").exists():
        print("corpus gelé : refus de modifier (supprimer FROZEN.json volontairement pour une v2)", file=sys.stderr)
        return 2
    cands = json.loads((CORPUS / "candidates.json").read_text("utf-8"))["candidates"]
    chosen = [c for c in cands if c.get("selected") and c.get("direct_pdf")]
    if not chosen:
        print("aucun candidat avec selected:true et direct_pdf:true dans candidates.json", file=sys.stderr)
        return 2
    DOCS.mkdir(parents=True, exist_ok=True)
    manifest, report = [], []
    for i, c in enumerate(chosen, 1):
        doc_id = f"fin_doc_{i:03d}"
        dest = DOCS / f"{doc_id}.pdf"
        try:
            ctype, size = download(c["source_url"], dest)
            entry = {
                "document_id": doc_id, "filename": dest.name, "company": c["company"], "title": c["title"],
                "reporting_period": c["reporting_period"], "document_type": c["document_type"],
                "institution_type": c["institution_type"], "source_url": c["source_url"],
                "source_domain": c["source_domain"], "pages": pdf_pages(dest),
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": sha256_file(dest), "bytes": size, "content_type": ctype,
            }
            manifest.append(entry)
            report.append({"candidate_id": c["candidate_id"], "document_id": doc_id, "ok": True, "pages": entry["pages"]})
            print(f"ok   {doc_id} {entry['pages']:>4} p  {c['company']}")
        except Exception as e:  # noqa: BLE001 — on consigne et on continue
            dest.unlink(missing_ok=True)
            report.append({"candidate_id": c["candidate_id"], "ok": False, "error": f"{type(e).__name__}: {e}"})
            print(f"FAIL {c['candidate_id']} {c['source_url']} : {e}", file=sys.stderr)
    (CORPUS / "fetch_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    (CORPUS / "manifest.json").write_text(json.dumps(
        {"corpus": "finance_corpus_v1", "n_documents": len(manifest), "total_pages": sum(m["pages"] for m in manifest),
         "documents": manifest}, indent=2, ensure_ascii=False), "utf-8")
    print(f"{len(manifest)} documents, {sum(m['pages'] for m in manifest)} pages")
    return 0 if manifest else 1


def freeze(args) -> int:
    path = CORPUS / "manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    bad = []
    for d in manifest["documents"]:
        p = DOCS / d["filename"]
        if not p.exists() or sha256_file(p) != d["sha256"]:
            bad.append(d["document_id"])
    if bad:
        print(f"gel refusé : fichiers absents ou modifiés : {bad}", file=sys.stderr)
        return 2
    (CORPUS / "FROZEN.json").write_text(json.dumps({
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(path), "n_documents": manifest["n_documents"],
        "total_pages": manifest["total_pages"]}, indent=2), "utf-8")
    for p in [path, *(DOCS / d["filename"] for d in manifest["documents"])]:
        os.chmod(p, 0o444)
    print(f"corpus gelé : {manifest['n_documents']} documents, {manifest['total_pages']} pages")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    sys.exit(freeze(a) if a.freeze else build(a))
