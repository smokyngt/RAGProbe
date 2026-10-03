#!/usr/bin/env python3
"""Download the selected documents (corpus/candidates.json -> "selected": true) and maintain the frozen corpus.

    python tools/fetch_corpus.py --label v1.2   # download every selected candidate not yet in the manifest,
                                                # append it with a new id, then re-freeze (history kept)
    python tools/fetch_corpus.py --freeze       # verify every SHA-256; re-freeze only if the manifest changed

Rules:
  - document ids are never reused or renumbered; existing files are re-verified before anything is added;
  - provenance per document: source_url, domain, retrieval time, SHA-256, size, page count (pdfinfo), batch label;
  - a download that is not a PDF, too large, or suspiciously short (< 4 pages, usually a printed web page) is rejected
    and logged in corpus/fetch_report_<label>.json, never silently skipped;
  - corpus/FROZEN.json records the current freeze and the full freeze history.
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
MANIFEST = CORPUS / "manifest.json"
FROZEN = CORPUS / "FROZEN.json"
UA = "FinanceBench-corpus-builder/1.0 (research; public documents only)"
MAX_BYTES = 250 * 1024 * 1024
MIN_PAGES = 4


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
        raise ValueError("pdfinfo: page count not found")
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
                    raise ValueError(f"file larger than {MAX_BYTES >> 20} MB")
                f.write(chunk)
    with open(tmp, "rb") as f:
        if f.read(5) != b"%PDF-":
            tmp.unlink()
            raise ValueError(f"not a PDF (Content-Type: {ctype})")
    tmp.replace(dest)
    return ctype, size


def _write_readonly(path: Path, text: str) -> None:
    if path.exists():
        os.chmod(path, 0o644)
    path.write_text(text, "utf-8")
    os.chmod(path, 0o444)


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text("utf-8"))
    return {"corpus": "finance_corpus_v1", "n_documents": 0, "total_pages": 0, "documents": []}


def verify(manifest: dict) -> list[str]:
    """Ids of documents whose file is missing or whose SHA-256 changed."""
    return [d["document_id"] for d in manifest["documents"]
            if not (DOCS / d["filename"]).exists() or sha256_file(DOCS / d["filename"]) != d["sha256"]]


def fetch(label: str) -> int:
    manifest = load_manifest()
    if bad := verify(manifest):
        print(f"refused: existing documents missing or modified: {bad}", file=sys.stderr)
        return 2
    known = {d["source_url"] for d in manifest["documents"]}
    todo = [c for c in json.loads((CORPUS / "candidates.json").read_text("utf-8"))["candidates"]
            if c.get("selected") and c.get("direct_pdf") and c["source_url"] not in known]
    if not todo:
        print("nothing to add (no selected candidate outside the manifest)")
        return 0
    DOCS.mkdir(parents=True, exist_ok=True)
    last = max((int(d["document_id"].rsplit("_", 1)[-1]) for d in manifest["documents"]), default=0)
    report, added = [], []
    for c in todo:
        doc_id = f"fin_doc_{last + len(added) + 1:03d}"  # ids are never reused
        dest = DOCS / f"{doc_id}.pdf"
        try:
            ctype, size = download(c["source_url"], dest)
            pages = pdf_pages(dest)
            if pages < MIN_PAGES and not c.get("allow_short"):
                raise ValueError(f"only {pages} pages: suspicious (printed web page?). "
                                 "Set allow_short: true in candidates.json if genuine")
            entry = {
                "document_id": doc_id, "filename": dest.name, "company": c["company"], "title": c["title"],
                "reporting_period": c["reporting_period"], "document_type": c["document_type"],
                "institution_type": c["institution_type"], "source_url": c["source_url"],
                "source_domain": c["source_domain"], "pages": pages,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": sha256_file(dest), "bytes": size, "content_type": ctype,
                "language": c.get("language", "en"), "added_in": label,
            }
            os.chmod(dest, 0o444)
            added.append(entry)
            report.append({"candidate_id": c["candidate_id"], "document_id": doc_id, "ok": True, "pages": pages})
            print(f"ok   {doc_id} {pages:>4} p  {c['company']} — {c['title']}")
        except Exception as e:  # noqa: BLE001 — logged and reported, never hidden
            dest.unlink(missing_ok=True)
            report.append({"candidate_id": c["candidate_id"], "ok": False, "error": f"{type(e).__name__}: {e}"})
            print(f"FAIL {c['candidate_id']} {c['source_url']}: {e}", file=sys.stderr)
    (CORPUS / f"fetch_report_{label}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    if not added:
        return 1
    manifest["documents"].extend(added)
    manifest["n_documents"] = len(manifest["documents"])
    manifest["total_pages"] = sum(d["pages"] for d in manifest["documents"])
    _write_readonly(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
    return freeze(last_addition={"label": label, "added": [d["document_id"] for d in added]})


def freeze(last_addition: dict | None = None) -> int:
    """Verify every document; record a new freeze only if the manifest changed (previous freeze moves to history)."""
    manifest = load_manifest()
    if bad := verify(manifest):
        print(f"freeze refused: documents missing or modified: {bad}", file=sys.stderr)
        return 2
    digest = sha256_file(MANIFEST)
    previous = json.loads(FROZEN.read_text("utf-8")) if FROZEN.exists() else None
    if previous and previous.get("manifest_sha256") == digest:
        print(f"verified: {manifest['n_documents']} documents, {manifest['total_pages']} pages, unchanged since "
              f"{previous['frozen_at']}")
        return 0
    history = list(previous.get("freeze_history", [])) if previous else []
    if previous:
        history.append({k: previous[k] for k in ("frozen_at", "manifest_sha256", "n_documents", "total_pages") if k in previous})
    record = {"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "manifest_sha256": digest,
              "n_documents": manifest["n_documents"], "total_pages": manifest["total_pages"], "freeze_history": history}
    if last_addition or (previous and "last_addition" in previous):
        record["last_addition"] = last_addition or previous["last_addition"]
    _write_readonly(FROZEN, json.dumps(record, indent=2))
    for d in manifest["documents"]:
        os.chmod(DOCS / d["filename"], 0o444)
    print(f"frozen: {manifest['n_documents']} documents, {manifest['total_pages']} pages")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freeze", action="store_true", help="verify the corpus and re-freeze if the manifest changed")
    ap.add_argument("--label", default="addition", help="batch label recorded for downloaded documents (e.g. v1.2)")
    a = ap.parse_args()
    sys.exit(freeze() if a.freeze else fetch(a.label))
