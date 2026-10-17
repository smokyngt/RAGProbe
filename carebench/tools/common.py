"""Shared helpers for CareBench: page texts of corpus documents (for evidence checking)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def eml_text(path: Path) -> str:
    import email
    import email.policy
    msg = email.message_from_bytes(Path(path).read_bytes(), policy=email.policy.default)
    head = [f"{k}: {msg[k]}" for k in ("From", "To", "Cc", "Date", "Subject") if msg[k]]
    return "\n".join(head) + "\n\n" + msg.get_body(preferencelist=("plain",)).get_content()


def manifest() -> dict:
    return json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))


def document_pages(doc: dict) -> list[str]:
    """Page texts of a manifest entry: pdftotext for PDFs, the OCR reference for scans, headers + body for e-mails."""
    path = ROOT / "corpus" / "documents" / doc["filename"]
    if doc["filename"].endswith(".eml"):
        return [eml_text(path)]
    if doc.get("scanned"):
        text = (ROOT / "corpus" / "ocr_reference" / f"{doc['document_id']}.txt").read_text("utf-8")
    else:
        text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    pages = text.split("\f")
    return pages[:-1] if pages and pages[-1] == "" else pages
