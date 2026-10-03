"""Tests de l'outillage FinanceBench sur de petits PDF SYNTHÉTIQUES générés ici (aucune donnée réelle)."""
import json
from pathlib import Path

import pytest

from extract_pages import pdf_page_texts
from validate_dataset import evidence_on_page, norm, parse_number, run, safe_eval


def make_pdf(path: Path, pages: list[list[str]]) -> None:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        content = "BT /F1 11 Tf 40 760 Td 14 TL " + " ".join(f"({l.replace('(', '[').replace(')', ']')}) Tj T*" for l in lines) + " ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs) + 2} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def test_parse_number():
    assert parse_number("1,284") == 1284 and parse_number("(213)") == -213 and parse_number("12.5%") == 12.5
    assert parse_number("1.284,5") == 1284.5 and parse_number("1 284") == 1284 and parse_number("€1,284.3") == 1284.3
    assert parse_number("−45") == -45 and parse_number("12,5") == 12.5
    with pytest.raises(ValueError):
        parse_number("n/a")


def test_safe_eval():
    assert safe_eval("(2025_revenue - 2024_revenue) / 2024_revenue", {"2024_revenue": 120.0, "2025_revenue": 150.0}) == 0.25
    assert safe_eval("a / b", {"a": 1, "b": 4}) == 0.25
    for bad in ("__import__('os').system('x')", "a.real", "open('f')", "a + zzz"):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval(bad, {"a": 1})


def test_evidence_matching_normalisation():
    page = "Net  interest income\n  1,284   1,198 – total"
    assert evidence_on_page("Net interest income 1,284 1,198 - total", page)
    assert evidence_on_page("Net interest income … 1,198", page)
    assert not evidence_on_page("1,198 … Net interest income", page)  # l'ordre compte
    assert not evidence_on_page("Net interest income 9,999", page)
    assert norm("a b") == "a b"


def test_pdf_pages(tmp_path):
    make_pdf(tmp_path / "x.pdf", [["Page one text"], ["Page two text"]])
    pages = pdf_page_texts(tmp_path / "x.pdf")
    assert len(pages) == 2 and "Page two" in pages[1]


@pytest.fixture
def project(tmp_path):
    (tmp_path / "corpus" / "documents").mkdir(parents=True)
    make_pdf(tmp_path / "corpus" / "documents" / "fin_doc_001.pdf",
             [["Cover page"], ["Revenue EUR million 2025: 1,284 2024: 1,100", "Operating expenses (213)"]])
    make_pdf(tmp_path / "corpus" / "documents" / "fin_doc_002.pdf", [["Revenue USD thousand 2025: 500"]])
    (tmp_path / "corpus" / "manifest.json").write_text(json.dumps({"documents": [
        {"document_id": "fin_doc_001", "filename": "fin_doc_001.pdf", "pages": 2},
        {"document_id": "fin_doc_002", "filename": "fin_doc_002.pdf", "pages": 1}]}))
    (tmp_path / "corpus" / "FROZEN.json").write_text("{}")
    (tmp_path / "datasets").mkdir()
    return tmp_path


def ex(qid, qtype="direct", evidence=None, answerable=True, calc=None, multi=False, tier="silver", answer="EUR 1.284 billion"):
    return {"id": qid, "question": "What was the revenue in 2025 in the report?", "reference_answer": answer,
            "evidence": evidence if evidence is not None else [{"document_id": "fin_doc_001", "page": 2,
                                                                "text": "Revenue EUR million 2025: 1,284"}],
            "metadata": {"type": qtype, "difficulty": "easy", "requires_calculation": calc is not None,
                         "requires_multiple_documents": multi, "answerable": answerable, "tier": tier},
            "calculation": calc}


CALC = {"inputs": {"2024_revenue": 1.1e9, "2025_revenue": 1.284e9},
        "operation": "(2025_revenue - 2024_revenue) / 2024_revenue", "result": 0.16727272727272727,
        "input_sources": {"2024_revenue": {"evidence_index": 0, "raw": "1,100", "unit": "EUR million", "scale": 1e6},
                          "2025_revenue": {"evidence_index": 0, "raw": "1,284", "unit": "EUR million", "scale": 1e6}}}
CALC_EV = [{"document_id": "fin_doc_001", "page": 2, "text": "Revenue EUR million 2025: 1,284 2024: 1,100"}]


def review(qid, status="verified", method="manual", recompute=None):
    r = {"status": status, "method": method, "reviewer": "t", "notes": "doubt" if status == "flagged" else "",
         "checks": {k: True for k in ("answer_correctness", "numerical_correctness", "currency", "units",
                                      "reporting_period", "entity", "evidence_location", "calculation",
                                      "ambiguity", "completeness")}}
    if recompute is not None:
        r["independent_recompute"] = {"result": recompute, "matches": True}
    return r


def write(project, examples, reviews):
    (project / "datasets" / "d.jsonl").write_text("".join(json.dumps(e) + "\n" for e in examples))
    (project / "datasets" / "r.json").write_text(json.dumps({"reviews": reviews}))
    return run(project, project / "datasets" / "d.jsonl", project / "datasets" / "r.json",
               project / "datasets" / "final.jsonl", export=True)


def test_valid_dataset_exports_only_verified(project, capsys):
    examples = [ex("fin_q_001"), ex("fin_q_002", "calculation", CALC_EV, calc=CALC),
                ex("fin_q_003", "negative", [], answerable=False, answer="This cannot be established from the documents."),
                ex("fin_q_004")]
    reviews = {"fin_q_001": review("fin_q_001"), "fin_q_002": review("fin_q_002", recompute=0.16727272727272727),
               "fin_q_003": review("fin_q_003"), "fin_q_004": review("fin_q_004", "flagged")}
    assert write(project, examples, reviews) == 0
    final = (project / "datasets" / "final.jsonl").read_text().splitlines()
    assert [json.loads(l)["id"] for l in final] == ["fin_q_001", "fin_q_002", "fin_q_003"]  # le flagged est exclu


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e["evidence"][0].update(text="Revenue EUR million 2025: 9,999"), "not found verbatim"),
    (lambda e: e["evidence"][0].update(page=9), "page 9"),
    (lambda e: e["evidence"][0].update(document_id="fin_doc_099"), "unknown document"),
])
def test_bad_evidence_is_rejected(project, capsys, mutate, needle):
    e = ex("fin_q_001")
    mutate(e)
    assert write(project, [e], {"fin_q_001": review("fin_q_001")}) == 1
    assert needle in capsys.readouterr().out


def test_calculation_errors(project, capsys):
    wrong_result = {**CALC, "result": 0.25}
    wrong_unit = {**CALC, "inputs": {**CALC["inputs"], "2025_revenue": 1284.0}}  # unité « million » perdue
    raw_missing = json.loads(json.dumps(CALC))
    raw_missing["input_sources"]["2025_revenue"]["raw"] = "1,285"
    for calc in (wrong_result, wrong_unit, raw_missing):
        e = ex("fin_q_001", "calculation", CALC_EV, calc=calc)
        assert write(project, [e], {"fin_q_001": review("fin_q_001", recompute=calc["result"])}) == 1
    out = capsys.readouterr().out
    assert "annotated 0.25" in out and "unit/scale" in out and "absent from evidence" in out


def test_review_rules(project, capsys):
    assert write(project, [ex("fin_q_001")], {}) == 1  # pas de revue
    assert "no review entry" in capsys.readouterr().out
    assert write(project, [ex("fin_q_001", tier="gold")], {"fin_q_001": review("fin_q_001", method="automated")}) == 1
    assert "gold requires a manual" in capsys.readouterr().out
    bad = review("fin_q_001")
    bad["checks"]["units"] = False
    assert write(project, [ex("fin_q_001")], {"fin_q_001": bad}) == 1
    assert "checks not passed" in capsys.readouterr().out
    missing_recalc = write(project, [ex("fin_q_001", "calculation", CALC_EV, calc=CALC)], {"fin_q_001": review("fin_q_001")})
    assert missing_recalc == 1 and "independent recompute" in capsys.readouterr().out


def test_llm_blind_reverify_must_not_claim_human_review(project, capsys):
    r = review("fin_q_001", method="llm_blind_reverify")
    assert write(project, [ex("fin_q_001", tier="gold")], {"fin_q_001": r}) == 1
    assert "human_reviewed=false" in capsys.readouterr().out
    r["human_reviewed"] = False
    assert write(project, [ex("fin_q_001", tier="gold")], {"fin_q_001": r}) == 0


def test_no_review_mode(project):
    (project / "datasets" / "d.jsonl").write_text(json.dumps(ex("fin_q_001")) + "\n")
    assert run(project, project / "datasets" / "d.jsonl", project / "datasets" / "missing.json",
               project / "datasets" / "f.jsonl", export=False, no_review=True) == 0


def test_schema_consistency(project, capsys):
    multi_doc_flag_wrong = ex("fin_q_001", multi=True)
    assert write(project, [multi_doc_flag_wrong], {"fin_q_001": review("fin_q_001")}) == 1
    assert "requires_multiple_documents" in capsys.readouterr().out
    assert write(project, [ex("fin_q_001"), ex("fin_q_001")], {"fin_q_001": review("fin_q_001")}) == 1
    assert "duplicate id" in capsys.readouterr().out
    assert write(project, [ex("fin_q_005", "negative", answerable=True)], {}) == 1
