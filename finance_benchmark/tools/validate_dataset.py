#!/usr/bin/env python3
"""Automatic validation of the dataset (merged draft) and of the review file; export of verified examples only.

    python tools/validate_dataset.py                 # checks + distribution report
    python tools/validate_dataset.py --no-review     # annotator self-check (no review file required)
    python tools/validate_dataset.py --export        # writes datasets/finance_benchmark_v1.jsonl (`verified` examples only)

Automatic checks (they do NOT replace reading the source document):
  - schema, unique ids, document_id/page present in corpus/manifest.json;
  - every `evidence.text` appears VERBATIM on the cited page of the PDF ("…" separates fragments, in order);
  - calculations: the operation is re-evaluated (restricted AST) and equals `result`; every input is found as printed
    (`raw`) in the cited evidence and raw × scale = value (units never disappear silently);
  - flag consistency (multi-document, calculation, unanswerable without evidence);
  - review: one entry per question, 10 checks filled in, matching independent recompute; tier `gold` needs a manual or
    llm_blind_reverify review, and llm_blind_reverify must declare human_reviewed=false.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parent.parent
QTYPES = ("direct", "table", "temporal", "calculation", "multi_evidence", "multi_document", "definition", "risk", "negative")
TARGET_50 = {"direct": 10, "table": 10, "temporal": 8, "calculation": 7, "multi_evidence": 5, "multi_document": 4,
             "definition": 3, "negative": 3}
STYLES = ("lookup", "superlative", "ranking", "yes_no", "comparison", "list", "count", "trend", "explanatory", "conditional")
FAILURE_MODES = ("same_metric_multiple_years", "similar_table_labels", "multiple_entities", "footnote",
                 "terminology_mismatch", "unit_mismatch", "split_across_pages", "header_dependency",
                 "deep_in_report", "multi_evidence_combination")
REVIEW_CHECKS = ("answer_correctness", "numerical_correctness", "currency", "units", "reporting_period", "entity",
                 "evidence_location", "calculation", "ambiguity", "completeness")
METHODS = ("manual", "manual_sample", "llm_blind_reverify", "automated")
NEGATIVE_PHRASES = ("cannot be established", "cannot be determined", "not provided", "does not provide",
                    "ne peut pas être établi", "n'est pas fourni", "not disclosed", "insufficient")


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_S):
    document_id: str
    page: int = Field(ge=1)
    text: str = Field(min_length=3)


class InputSource(_S):
    evidence_index: int = Field(ge=0)
    raw: str  # tel qu'imprimé dans le document : "1,284", "(213)", "12.5%"
    unit: str  # "€ million", "$ thousand", "%", "basis points"...
    scale: float  # multiplicateur vers l'unité de base : 1e6 pour "million", 0.01 pour "%"


class Calculation(_S):
    inputs: dict[str, float]
    operation: str
    result: float
    input_sources: dict[str, InputSource] = Field(default_factory=dict)


class Metadata(_S):
    type: Literal[QTYPES]  # type: ignore[valid-type]
    difficulty: Literal["easy", "medium", "hard"]
    requires_calculation: bool
    requires_multiple_documents: bool
    answerable: bool = True
    tier: Literal["gold", "silver"] = "silver"
    style: Literal[STYLES] = "lookup"  # type: ignore[valid-type]  # form of the question (orthogonal to `type`)
    topic: str | None = None  # e.g. "risk:liquidity", "capital:CET1", "profitability"
    failure_modes: list[Literal[FAILURE_MODES]] = Field(default_factory=list)  # type: ignore[valid-type]


class Example(_S):
    id: str = Field(pattern=r"^fin_q_\d{3,4}$")
    question: str = Field(min_length=10)
    reference_answer: str = Field(min_length=3)
    evidence: list[Evidence]
    metadata: Metadata
    calculation: Calculation | None = None

    @model_validator(mode="after")
    def _consistency(self):
        m, ev = self.metadata, self.evidence
        if not m.answerable and ev:
            raise ValueError("unanswerable question: evidence must be empty")
        if m.answerable and not ev:
            raise ValueError("empty evidence for an answerable question")
        if m.type == "negative" and m.answerable:
            raise ValueError("type negative implies answerable=false")
        if m.requires_calculation != (self.calculation is not None):
            raise ValueError("requires_calculation inconsistent with the presence of `calculation`")
        multi = len({e.document_id for e in ev}) > 1
        if m.requires_multiple_documents != multi:
            raise ValueError("requires_multiple_documents inconsistent with the cited documents")
        if m.type == "multi_document" and not multi:
            raise ValueError("type multi_document: evidence comes from a single document")
        if m.type == "multi_evidence" and len(ev) < 2:
            raise ValueError("type multi_evidence: at least 2 evidence items required")
        if self.calculation and m.type not in ("calculation", "temporal", "multi_document", "multi_evidence"):
            raise ValueError("`calculation` is reserved for types calculation/temporal/multi_*")
        return self


# ---------- texte des pages ----------

_DASH = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
_QUOTE = {ord("’"): "'", ord("‘"): "'", ord("“"): '"', ord("”"): '"'}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_DASH).translate(_QUOTE)
    return " ".join(text.split())


def evidence_on_page(evidence: str, page_text: str) -> bool:
    """Citation verbatim ; « … » / « [...] » séparent des fragments qui doivent apparaître dans l'ordre."""
    page, pos = norm(page_text), 0
    for frag in re.split(r"…|\[\.\.\.\]|\.\.\.", evidence):
        frag = norm(frag)
        if not frag:
            continue
        i = page.find(frag, pos)
        if i < 0:
            return False
        pos = i + len(frag)
    return True


def default_page_loader(root: Path) -> Callable[[str], list[str]]:
    from extract_pages import pdf_page_texts  # tools/ est dans sys.path quand le script est lancé

    manifest = json.loads((root / "corpus" / "manifest.json").read_text("utf-8"))
    files = {d["document_id"]: root / "corpus" / "documents" / d["filename"] for d in manifest["documents"]}
    cache: dict[str, list[str]] = {}

    def load(doc_id: str) -> list[str]:
        if doc_id not in cache:
            cache[doc_id] = pdf_page_texts(files[doc_id])
        return cache[doc_id]
    return load


# ---------- nombres et calculs ----------

def parse_number(raw: str) -> float:
    """'1,284' -> 1284 ; '(213)' -> -213 ; '12.5%' -> 12.5 ; '1.284,5' -> 1284.5 ; '1 284' -> 1284."""
    s = unicodedata.normalize("NFKC", raw).translate(_DASH).strip()
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = re.sub(r"[^\d.,\s']", "", s).replace("'", "").replace(" ", "")
    if not s:
        raise ValueError(f"aucun chiffre dans '{raw}'")
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    val = float(s)
    return -val if neg else val


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult,
            ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Call)


def safe_eval(operation: str, inputs: dict[str, float]) -> float:
    """Évalue l'opération avec un AST restreint. Les noms d'entrée (ex. '2025_revenue') sont d'abord remplacés."""
    expr, env = operation, {}
    for i, key in enumerate(sorted(inputs, key=len, reverse=True)):
        expr = re.sub(rf"(?<![\w.]){re.escape(key)}(?![\w])", f"v{i}", expr)
        env[f"v{i}"] = inputs[key]
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"élément interdit dans l'opération : {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in env and node.id != "abs":
            raise ValueError(f"nom inconnu dans l'opération : {node.id}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id == "abs"):
            raise ValueError("seul abs() est autorisé")
    return float(eval(compile(tree, "<op>", "eval"), {"__builtins__": {}, "abs": abs}, env))  # noqa: S307


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


# ---------- validation ----------

class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, qid: str, msg: str):
        self.errors.append(f"{qid}: {msg}")

    def warn(self, qid: str, msg: str):
        self.warnings.append(f"{qid}: {msg}")


def check_example(ex: Example, pages: dict[str, int], load: Callable[[str], list[str]], rep: Report) -> None:
    for i, e in enumerate(ex.evidence):
        if e.document_id not in pages:
            rep.err(ex.id, f"evidence[{i}] : unknown document {e.document_id}")
            continue
        if e.page > pages[e.document_id]:
            rep.err(ex.id, f"evidence[{i}] : page {e.page} > {pages[e.document_id]}")
            continue
        if not evidence_on_page(e.text, load(e.document_id)[e.page - 1]):
            rep.err(ex.id, f"evidence[{i}] : texte not found verbatim p.{e.page} de {e.document_id}")
    if not ex.metadata.answerable and not any(p in ex.reference_answer.lower() for p in NEGATIVE_PHRASES):
        rep.warn(ex.id, "negative answer: 'cannot be established…' wording expected")
    c = ex.calculation
    if not c:
        return
    try:
        got = safe_eval(c.operation, c.inputs)
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        rep.err(ex.id, f"calculation: {e}")
        return
    if not close(got, c.result):
        rep.err(ex.id, f"calculation: operation gives {got!r}, annotated {c.result!r}")
    for name, value in c.inputs.items():
        src = c.input_sources.get(name)
        if not src:
            rep.err(ex.id, f"calculation: entrée '{name}' has no input_sources (raw/unit/scale are mandatory)")
            continue
        if src.evidence_index >= len(ex.evidence):
            rep.err(ex.id, f"calculation: '{name}' points to a non-existent evidence item")
            continue
        if norm(src.raw) not in norm(ex.evidence[src.evidence_index].text):
            rep.err(ex.id, f"calculation: '{name}' raw '{src.raw}' absent from evidence[{src.evidence_index}]")
        try:
            if not close(parse_number(src.raw) * src.scale, value):
                rep.err(ex.id, f"calculation: '{name}' {src.raw} × {src.scale} ≠ {value} (unit/scale?)")
        except ValueError as e:
            rep.err(ex.id, f"calculation: '{name}' : {e}")


def check_review(examples: list[Example], review: dict, rep: Report) -> dict[str, str]:
    reviews, status = review.get("reviews", {}), {}
    for ex in examples:
        r = reviews.get(ex.id)
        if r is None:
            rep.err(ex.id, "no review entry")
            continue
        checks = r.get("checks", {})
        missing = [k for k in REVIEW_CHECKS if k not in checks]
        if missing:
            rep.err(ex.id, f"review: missing checks {missing}")
        st, method = r.get("status"), r.get("method")
        status[ex.id] = st
        if st not in ("verified", "flagged"):
            rep.err(ex.id, "review: status must be verified|flagged")
        if method not in METHODS:
            rep.err(ex.id, f"review: method must be one of {METHODS}")
        if st == "verified":
            failed = [k for k in REVIEW_CHECKS if checks.get(k) not in (True, "n/a")]
            if failed:
                rep.err(ex.id, f"review: verified mais checks not passed {failed}")
            if ex.calculation:
                rc = r.get("independent_recompute")
                if not rc or not close(float(rc.get("result", math.nan)), ex.calculation.result) or rc.get("matches") is not True:
                    rep.err(ex.id, "review: independent recompute missing or different")
            if ex.metadata.tier == "gold" and method not in ("manual", "llm_blind_reverify"):
                rep.err(ex.id, "tier gold requires a manual or llm_blind_reverify review (not automated)")
            if method == "llm_blind_reverify" and r.get("human_reviewed") is not False:
                rep.err(ex.id, "review: llm_blind_reverify must declare human_reviewed=false (no mislabelling)")
        if st == "flagged" and not r.get("notes"):
            rep.err(ex.id, "review: a flagged example must explain the doubt (notes)")
    extra = set(reviews) - {e.id for e in examples}
    for qid in sorted(extra):
        rep.warn(qid, "review entry without matching question")
    return status


def distribution(examples: list[Example]) -> str:
    n = len(examples)
    types = Counter(e.metadata.type for e in examples)
    scale = n / sum(TARGET_50.values()) if n else 0
    lines = [f"{n} examples", "type             n   target (scaled)"]
    for t in QTYPES:
        lines.append(f"{t:<16}{types.get(t, 0):>3}   {TARGET_50.get(t, 0) * scale:>5.1f}")
    lines.append("tier : " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(e.metadata.tier for e in examples).items())))
    st = Counter(e.metadata.style for e in examples)
    lines.append("styles: " + ", ".join(f"{k}={st[k]}" for k in STYLES if st[k]))
    lines.append("difficulty: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(e.metadata.difficulty for e in examples).items())))
    fm = Counter(f for e in examples for f in e.metadata.failure_modes)
    lines.append("failure modes covered: " + (", ".join(f"{k}={fm[k]}" for k in FAILURE_MODES if fm[k]) or "none"))
    return "\n".join(lines)


def load_examples(path: Path, rep: Report) -> list[Example]:
    out, seen = [], set()
    for ln, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            ex = Example.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as e:
            rep.err(f"ligne {ln}", str(e).replace("\n", " "))
            continue
        if ex.id in seen:
            rep.err(ex.id, "duplicate id")
        seen.add(ex.id)
        out.append(ex)
    return out


def run(root: Path, draft: Path, review_path: Path, final: Path, export: bool,
        no_review: bool = False, load: Callable[[str], list[str]] | None = None) -> int:
    rep = Report()
    manifest = json.loads((root / "corpus" / "manifest.json").read_text("utf-8"))
    pages = {d["document_id"]: d["pages"] for d in manifest["documents"]}
    if not (root / "corpus" / "FROZEN.json").exists():
        rep.warn("corpus", "corpus not frozen (tools/fetch_corpus.py --freeze): annotating a moving base")
    load = load or default_page_loader(root)
    examples = load_examples(draft, rep)
    for ex in examples:
        check_example(ex, pages, load, rep)
    status = {}
    if review_path.exists():
        status = check_review(examples, json.loads(review_path.read_text("utf-8")), rep)
    elif not no_review:
        rep.err("review", f"{review_path.name} missing: the independent validation pass has not happened")
    print(distribution(examples))
    for w in rep.warnings:
        print("WARN", w)
    for e in rep.errors:
        print("ERR ", e)
    n_ok = sum(s == "verified" for s in status.values())
    print(f"\nverified={n_ok} flagged={sum(s == 'flagged' for s in status.values())} errors={len(rep.errors)}")
    if export:
        if rep.errors:
            print("export refused: fix the errors first", file=sys.stderr)
            return 1
        verified = [e for e in examples if status.get(e.id) == "verified"]
        final.write_text("".join(e.model_dump_json(exclude_defaults=False) + "\n" for e in verified), "utf-8")
        print(f"wrote {final} ({len(verified)} verified examples; flagged ones stay in the review file)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draft", default=str(ROOT / "annotation" / "merged_draft.jsonl"))
    ap.add_argument("--review", default=str(ROOT / "datasets" / "finance_benchmark_v1_review.json"))
    ap.add_argument("--final", default=str(ROOT / "datasets" / "finance_benchmark_v1.jsonl"))
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--no-review", action="store_true", help="draft self-check: skip the review-file requirement")
    a = ap.parse_args()
    sys.exit(run(ROOT, Path(a.draft), Path(a.review), Path(a.final), a.export, a.no_review))
