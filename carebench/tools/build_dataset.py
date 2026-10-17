#!/usr/bin/env python3
"""Build the CareBench dataset: 21 clinical-document questions, 41 follow-ups, expected answers computed from scenario.py.

    python carebench/tools/build_dataset.py     # -> datasets/carebench_v1.jsonl (+ simple export, conversations, stats)

Each main question can have follow-up questions (`metadata.follow_up_of` = the main question id, `metadata.turn` = 2, 3...).
A follow-up row has two phrasings: `question` is self-contained (can be asked on its own), `question_natural` is how a
clinician would really ask it in the conversation ("And on the 17th?") and needs the previous turns. Evidence is
located automatically: every quote is searched in the page texts, so a quote that is not in the corpus stops the build.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "finance_benchmark" / "tools"))
import scenario as S  # noqa: E402
from common import ROOT, document_pages, manifest  # noqa: E402
from scenario import D, fd  # noqa: E402
import validate_dataset as fb  # noqa: E402

MAN = {d["document_id"]: d for d in manifest()["documents"]}
_PAGES: dict[str, list[str]] = {}


def pages(doc_id: str) -> list[str]:
    if doc_id not in _PAGES:
        _PAGES[doc_id] = document_pages(MAN[doc_id])
    return _PAGES[doc_id]


def ev(doc_id: str, text: str) -> dict:
    """Evidence item: the first page of the document that holds `text` verbatim ('…' separates ordered fragments)."""
    if doc_id not in MAN:
        raise SystemExit(f"unknown document {doc_id}")
    for i, p in enumerate(pages(doc_id), 1):
        if fb.evidence_on_page(text, p):
            return dict(document_id=doc_id, page=i, text=text)
    raise SystemExit(f"evidence not found in {doc_id}: {text!r}")


def kf(fact: str, value: str, *accept: str) -> dict:
    return dict(fact=fact, value=value, accept=list(accept))


def calc(inputs: dict, operation: str, result: float, sources: dict) -> dict:
    return dict(inputs=inputs, operation=operation, result=result,
                input_sources={k: dict(evidence_index=i, raw=raw, unit=unit, scale=scale) for k, (i, raw, unit, scale) in sources.items()})


ROWS: list[dict] = []
CONV: dict[str, list[str]] = {}


def main_q(n, question, natural, answer, kfs, evs, *, type, difficulty, style, domain, rule, fmt, modes, calculation=None,
           answerable=True, skills=(), safety=False):
    qid = f"care_q_{n:03d}"
    CONV[qid] = [qid]
    ROWS.append(_row(qid, question, natural, answer, kfs, evs, type, difficulty, style, domain, rule, fmt, modes, calculation,
                     answerable, skills, safety, None, 1, None, None))
    return qid


def follow_up(parent, kind, question, natural, answer, kfs, evs, *, type, difficulty, style, domain, rule, fmt, modes,
              calculation=None, answerable=True, skills=(), safety=False, depends=True):
    turn = len(CONV[parent]) + 1
    qid = f"{parent}_f{turn - 1}"
    CONV[parent].append(qid)
    ROWS.append(_row(qid, question, natural, answer, kfs, evs, type, difficulty, style, domain, rule, fmt, modes, calculation,
                     answerable, skills, safety, parent, turn, kind, depends))
    return qid


def _row(qid, question, natural, answer, kfs, evs, type_, difficulty, style, domain, rule, fmt, modes, calculation, answerable,
         skills, safety, parent, turn, kind, depends):
    return dict(
        id=qid, question=question, question_natural=natural, reference_answer=answer, key_facts=kfs, evidence=evs,
        metadata=dict(type=type_, difficulty=difficulty, requires_calculation=calculation is not None,
                      requires_multiple_documents=len({e["document_id"] for e in evs}) > 1, answerable=answerable, tier="silver",
                      style=style, topic=f"{domain}:{rule[:48].strip().lower().replace(' ', '_')}", failure_modes=modes,
                      domain=domain, clinical_rule=rule, output_format=fmt, reasoning_skills=list(skills), safety_relevant=safety,
                      conversation_id=parent or qid, turn=turn, follow_up_of=parent, follow_up_type=kind,
                      depends_on_previous_answer=depends if parent else None, follow_up_ids=[]),
        calculation=calculation)


def fmt_n(x: float, nd=1) -> str:
    return f"{x:.{nd}f}"


# =============================================================== questions
def build():
    # ---------------------------------------------------------------- 1. laboratory flags (Delaunay)
    L12, L05 = "LAB_Delaunay_Marc_2026-11-12", "LAB_Delaunay_Marc_2026-11-05"
    p = S.P["delaunay"]
    ab12 = S.abnormal(p, S.LAB_DELAUNAY[D(2026, 11, 12)])
    ab05 = S.abnormal(p, S.LAB_DELAUNAY[D(2026, 11, 5)])
    assert set(ab12) == {"K", "Urea", "Creat", "CRP", "ALT", "Alb", "Hb", "WBC"}, ab12
    rows12 = [("Potassium 5.4 mmol/L 3.5 - 5.0 H"), ("Urea 9.6 mmol/L 2.5 - 7.8 H"), ("Creatinine 128 µmol/L 60 - 110 H"),
              ("C-reactive protein 38 mg/L 0-5 H"), ("ALT 52 U/L 7 - 40 H"), ("Albumin 31 g/L 35 - 50 L"),
              ("Haemoglobin 118 g/L 130 - 175 L"), ("White cell count 11.8 10^9/L 4.0 - 10.0 H")]
    q1 = main_q(1,
        "Using the laboratory report of 12/11/2026 for Marc Delaunay (MRN 4471823), list every result that falls outside the printed reference interval. "
        "For each give the analyte, the result with its unit and the flag (H or L), and state how many results are abnormal.",
        "Which of Mr Delaunay's blood results from 12/11 are abnormal?",
        "Eight results are outside the reference interval on 12/11/2026: potassium 5.4 mmol/L (H), urea 9.6 mmol/L (H), creatinine 128 µmol/L (H), "
        "C-reactive protein 38 mg/L (H), ALT 52 U/L (H), albumin 31 g/L (L), haemoglobin 118 g/L (L) and white cell count 11.8 x10^9/L (H). "
        "All other analytes (sodium, chloride, glucose, AST, alkaline phosphatase, gamma-GT, bilirubin, calcium, magnesium, phosphate, TSH, ferritin, haematocrit, MCV, platelets) are within range.",
        [kf("number of abnormal results", "Eight", "8"), kf("potassium", "5.4"), kf("urea", "9.6"), kf("creatinine", "128"), kf("CRP", "38"),
         kf("ALT", "52"), kf("albumin", "31"), kf("haemoglobin", "118"), kf("white cell count", "11.8")],
        [ev(L12, r) for r in rows12],
        type="table", difficulty="easy", style="list", domain="laboratory", rule="Flag results outside the printed reference interval",
        fmt="table: analyte | result and unit | flag", modes=["header_dependency", "split_across_pages"], skills=["interval_comparison"])
    follow_up(q1, "compare_over_time",
        "Compare Marc Delaunay's laboratory reports of 12/11/2026 and 05/11/2026. Which of the eight abnormal results of 12/11/2026 were already outside the reference interval on 05/11/2026 "
        "(give the earlier value), and which are new? Treat a value exactly on a limit of the interval as within range.",
        "Were those already abnormal on the report from the week before?",
        "Already abnormal on 05/11/2026: urea 8.4 mmol/L, creatinine 121 µmol/L, C-reactive protein 96 mg/L, albumin 33 g/L, haemoglobin 122 g/L and white cell count 13.5 x10^9/L. "
        "New on 12/11/2026: potassium (4.9 mmol/L on 05/11/2026, within range) and ALT (38 U/L, within range). Platelets (150) and magnesium (0.70) sat exactly on a limit on 05/11/2026 and are within range.",
        [kf("new abnormal: potassium (previous value)", "4.9"), kf("new abnormal: ALT (previous value)", "38"), kf("urea previous", "8.4"),
         kf("creatinine previous", "121"), kf("CRP previous", "96"), kf("albumin previous", "33"), kf("haemoglobin previous", "122"), kf("WBC previous", "13.5")],
        [ev(L05, r) for r in ("Potassium 4.9 mmol/L 3.5 - 5.0", "Urea 8.4 mmol/L 2.5 - 7.8 H", "Creatinine 121 µmol/L 60 - 110 H", "C-reactive protein 96 mg/L 0-5 H",
                              "ALT 38 U/L 7 - 40", "Albumin 33 g/L 35 - 50 L", "Haemoglobin 122 g/L 130 - 175 L", "White cell count 13.5 10^9/L 4.0 - 10.0 H",
                              "Platelets 150 10^9/L 150 - 400", "Magnesium 0.70 mmol/L 0.70 - 1.05")],
        type="temporal", difficulty="medium", style="comparison", domain="laboratory", rule="Compare two reports; a value on the limit is in range",
        fmt="two lists: already abnormal (with earlier value) / new", modes=["same_analyte_multiple_dates", "threshold_boundary"], skills=["interval_comparison", "temporal_comparison"])
    follow_up(q1, "calculation",
        "By how much, in mg/L and in percent of the 05/11/2026 value, did Marc Delaunay's C-reactive protein change between the reports of 05/11/2026 and 12/11/2026?",
        "How much did the CRP come down?",
        "C-reactive protein fell from 96 mg/L on 05/11/2026 to 38 mg/L on 12/11/2026: a decrease of 58 mg/L, i.e. 60.4% of the earlier value. It remains above the reference interval (0-5 mg/L).",
        [kf("absolute change", "58 mg/L", "58"), kf("relative change", "60.4%", "60.42%", "60%")],
        [ev(L05, "C-reactive protein 96 mg/L 0-5 H"), ev(L12, "C-reactive protein 38 mg/L 0-5 H")],
        type="calculation", difficulty="easy", style="trend", domain="laboratory", rule="Percentage change between two results", fmt="two numbers",
        modes=["same_analyte_multiple_dates", "multi_document_join"], skills=["percentage_change"],
        calculation=calc({"crp_before": 96, "crp_after": 38}, "(crp_before - crp_after) / crp_before * 100", (96 - 38) / 96 * 100,
                         {"crp_before": (0, "96", "mg/L", 1), "crp_after": (1, "38", "mg/L", 1)}))

    # ---------------------------------------------------------------- 2. eGFR and enoxaparin (Ferrand)
    PR, F16, F17, FPR = "PHA-REN-02_Renal_Dose_Adjustment_Protocol_v4", "LAB_Ferrand_Odile_2026-11-16", "LAB_Ferrand_Odile_2026-11-17", "PRESC_Ferrand_Odile_2026-11-16"
    r1, r2 = S.ferrand_result(175, D(2026, 11, 16)), S.ferrand_result(105, D(2026, 11, 17))
    assert (r1["egfr"], r1["dose_mg"], r1["every_h"]) == (25, 60, 24) and (r2["egfr"], r2["every_h"]) == (47, 12)
    op = "142 * ((creat_umol / 88.4) / 0.7) ** -1.2 * 0.9938 ** age * 1.012"
    q2 = main_q(2,
        "Using protocol PHA-REN-02, estimate Odile Ferrand's (MRN 4480110) eGFR from the serum creatinine of 16/11/2026, then give the enoxaparin treatment-dose band, "
        "the calculated dose in mg (use her weight on the prescription chart), the prefilled syringe to use and the dosing interval. Round the eGFR to the nearest whole number.",
        "What enoxaparin regimen should Mrs Ferrand be on, given her kidney function on 16/11?",
        f"Creatinine 175 µmol/L = 1.98 mg/dL; for a 78-year-old woman the CKD-EPI 2021 equation gives an eGFR of {r1['egfr']} mL/min/1.73 m2. "
        "That is in the band 15 to 29: enoxaparin 1 mg/kg once daily. At 62 kg the calculated dose is 62 mg, rounded to the nearest prefilled syringe: 60 mg once daily.",
        [kf("eGFR", "25", "25 mL/min"), kf("band", "15 to 29", "15-29"), kf("calculated dose", "62 mg"), kf("syringe", "60 mg"), kf("interval", "once daily", "every 24 hours", "once a day")],
        [ev(F16, "Âge 78 ans … Créatinine 175 µmol/L"), ev(PR, "eGFR = 142 x min(Scr/kappa, 1)^alpha x max(Scr/kappa, 1)^-1.200 x 0.9938^Age x 1.012 [if female]"),
         ev(PR, "Female kappa = 0.7, alpha = -0.241"), ev(PR, "15 to 29 1 mg/kg once daily"), ev(FPR, "Poids 62 kg")],
        type="calculation", difficulty="hard", style="conditional", domain="pharmacy", rule="CKD-EPI 2021 eGFR then enoxaparin band", safety=True,
        fmt="eGFR | band | calculated dose | syringe | interval", modes=["unit_conversion", "french_document", "multi_document_join", "derived_value"],
        skills=["unit_conversion", "formula_evaluation", "table_lookup"],
        calculation=calc({"creat_umol": 175, "age": 78}, op, S.ckd_epi_2021(175, 78, True), {"creat_umol": (0, "175", "µmol/L", 1), "age": (0, "78", "years", 1)}))
    follow_up(q2, "hypothetical_variation",
        "Odile Ferrand's creatinine on 17/11/2026 was 105 µmol/L (age and weight unchanged). Repeat the calculation: eGFR, band and enoxaparin regimen (syringe and interval).",
        "And with the creatinine of the 17th?",
        f"Creatinine 105 µmol/L = 1.19 mg/dL gives an eGFR of {r2['egfr']} mL/min/1.73 m2, in the band 30 or above: 1 mg/kg every 12 hours, i.e. a 60 mg syringe every 12 hours.",
        [kf("eGFR", "47", "47 mL/min"), kf("band", "30 or above"), kf("interval", "every 12 hours", "twice daily", "12-hourly"), kf("syringe", "60 mg")],
        [ev(F17, "Âge 78 ans … Créatinine 105 µmol/L"), ev(PR, "30 or above 1 mg/kg every 12 hours")],
        type="calculation", difficulty="hard", style="conditional", domain="pharmacy", rule="CKD-EPI 2021 eGFR then enoxaparin band", safety=True,
        fmt="eGFR | band | syringe | interval", modes=["same_analyte_multiple_dates", "unit_conversion", "french_document", "hypothetical_variation"],
        skills=["unit_conversion", "formula_evaluation", "table_lookup"],
        calculation=calc({"creat_umol": 105, "age": 78}, op, S.ckd_epi_2021(105, 78, True), {"creat_umol": (0, "105", "µmol/L", 1), "age": (0, "78", "years", 1)}))
    follow_up(q2, "aggregate",
        "What is Odile Ferrand's total enoxaparin dose per 24 hours on 16/11/2026 and on 17/11/2026, using the regimens that apply to each day's creatinine?",
        "So how much enoxaparin does she get over a day on each of those days?",
        "On 16/11/2026 (eGFR 25, once daily) the total is 60 mg per day. On 17/11/2026 (eGFR 47, every 12 hours) it is 120 mg per day: the daily dose doubles while the dose per injection stays 60 mg.",
        [kf("total on 16/11", "60 mg per day", "60 mg"), kf("total on 17/11", "120 mg per day", "120 mg")],
        [ev(PR, "15 to 29 1 mg/kg once daily"), ev(PR, "30 or above 1 mg/kg every 12 hours")],
        type="multi_evidence", difficulty="medium", style="comparison", domain="pharmacy", rule="Daily dose from interval", fmt="two totals",
        modes=["hypothetical_variation", "derived_value"], skills=["arithmetic"], safety=True)

    # ---------------------------------------------------------------- 3. medication reconciliation (Marchand)
    ADMM, CRHM = "ADM_Marchand_Helene_2026-10-30", "CRH_Marchand_Helene_2026-11-09"
    q3 = main_q(3,
        "Compare the home medicines in Hélène Marchand's admission note (MRN 4476652, admitted 30/10/2026) with her discharge medicines (discharge summary of 09/11/2026). "
        "Classify every medicine as unchanged, dose changed (old dose to new dose), stopped or new.",
        "What changed in Mrs Marchand's medicines between admission and discharge?",
        "Dose changed: ramipril 5 mg to 2.5 mg once daily; atorvastatin 20 mg to 40 mg at night. Stopped: ibuprofen 400 mg when required. New: furosemide 40 mg once daily and apixaban 5 mg twice daily. "
        "Unchanged: bisoprolol 2.5 mg once daily, metformin 850 mg twice daily, aspirin 75 mg once daily and omeprazole 20 mg once daily.",
        [kf("ramipril change", "2.5 mg"), kf("atorvastatin change", "40 mg"), kf("stopped", "ibuprofen"), kf("new", "furosemide"), kf("new", "apixaban"),
         kf("unchanged", "bisoprolol"), kf("unchanged", "metformin")],
        [ev(ADMM, "Ramipril 5 mg once daily"), ev(ADMM, "Atorvastatin 20 mg at night"), ev(ADMM, "Ibuprofen 400 mg when required"),
         ev(CRHM, "Ramipril 2.5 mg once daily CHANGED"), ev(CRHM, "Atorvastatin 40 mg at night CHANGED"), ev(CRHM, "Ibuprofen 400 mg when required STOPPED"),
         ev(CRHM, "Furosemide 40 mg once daily NEW"), ev(CRHM, "Apixaban 5 mg twice daily NEW")],
        type="multi_document", difficulty="medium", style="list", domain="medication_safety", rule="Medication reconciliation admission vs discharge",
        fmt="four groups: unchanged | changed | stopped | new", modes=["multi_document_join", "french_document"], skills=["set_difference"], safety=True)
    follow_up(q3, "explain_why", "Why was Hélène Marchand's ramipril dose reduced at discharge?", "Why was the ramipril lowered?",
        "Because her potassium was 5.6 mmol/L on 04/11/2026: the dose was reduced from 5 mg to 2.5 mg once daily.",
        [kf("reason", "5.6 mmol/L", "5,6"), kf("date", "04/11/2026")],
        [ev(CRHM, "Ramipril - dose reduced from 5 mg: potassium 5.6 mmol/L on 04/11/2026")],
        type="direct", difficulty="easy", style="explanatory", domain="medication_safety", rule="Reason for a dose change", fmt="one sentence",
        modes=["french_document"], skills=["extraction"])
    follow_up(q3, "explain_why", "Why was Hélène Marchand's ibuprofen stopped?", "And the ibuprofen?",
        "Ibuprofen was stopped because of the acute kidney injury: NSAIDs are to be avoided.",
        [kf("reason", "acute kidney injury", "insuffisance rénale aiguë", "kidney injury")],
        [ev(CRHM, "Ibuprofen - stopped: acute kidney injury, avoid NSAIDs")],
        type="direct", difficulty="easy", style="explanatory", domain="medication_safety", rule="Reason for a stopped medicine", fmt="one sentence",
        modes=["french_document"], skills=["extraction"])

    # ---------------------------------------------------------------- 4. allergy conflict (Lefebvre)
    ADML, MARL, EML_L, ANTI = "ADM_Lefebvre_Yves_2026-11-10", "MAR_Lefebvre_Yves_2026-11-10", "2026-11-11_Pharmacist_intervention_Lefebvre_MRN-4483391", "PHA-ANT-01_Antibiotic_Prescribing_Policy_v7"
    q4 = main_q(4,
        "Compare the allergy recorded in Yves Lefebvre's admission note (MRN 4483391, 10/11/2026) with the allergy status and the administration record on his drug chart. "
        "Was any medicine given that conflicts with the documented allergy? If so, name the medicine and give the number, dates and times of the doses administered.",
        "Did Mr Lefebvre get anything he's allergic to?",
        "Yes. The admission note records a penicillin allergy (anaphylaxis, 2009) but the drug chart says no known drug allergies. Amoxicillin, a penicillin, was given three times: "
        "10/11/2026 at 14:10, 10/11/2026 at 22:05 and 11/11/2026 at 06:00. Doxycycline, given afterwards, is not a penicillin.",
        [kf("medicine", "amoxicillin"), kf("doses given", "three", "3"), kf("dose 1", "14:10"), kf("dose 2", "22:05"), kf("dose 3", "06:00"), kf("allergy", "penicillin")],
        [ev(ADML, "PENICILLIN - anaphylaxis (2009)"), ev(MARL, "Allergy status No known drug allergies (NKDA)"), ev(MARL, "Amoxicillin 1 g 10/11/2026 14:10 Nurse A. Roche"),
         ev(MARL, "Amoxicillin 1 g 10/11/2026 22:05 Nurse M. Dumas"), ev(MARL, "Amoxicillin 1 g 11/11/2026 06:00 Nurse M. Dumas")],
        type="multi_document", difficulty="medium", style="list", domain="medication_safety", rule="Documented allergy vs administered drug", safety=True,
        fmt="yes/no | medicine | number of doses | date and time of each", modes=["multi_document_join", "decoy_discontinued_drug", "terminology_mismatch"], skills=["drug_class_reasoning"])
    follow_up(q4, "drill_down", "What reaction to penicillin is documented in Yves Lefebvre's admission note?", "What was the reaction he had?",
        "Anaphylaxis in 2009: facial angioedema, urticaria and hypotension requiring adrenaline.",
        [kf("type", "anaphylaxis"), kf("year", "2009"), kf("angioedema", "angioedema"), kf("urticaria", "urticaria"), kf("hypotension", "hypotension")],
        [ev(ADML, "PENICILLIN - anaphylaxis (2009): facial angioedema, urticaria and hypotension requiring adrenaline.")],
        type="direct", difficulty="easy", style="lookup", domain="medication_safety", rule="Allergy details", fmt="one sentence", modes=[], skills=["extraction"], safety=True)
    follow_up(q4, "next_step", "According to antibiotic policy PHA-ANT-01, which antibiotic is first line for moderate community-acquired pneumonia in a patient with a severe penicillin allergy, "
        "and is it what Yves Lefebvre received after amoxicillin was stopped?", "What should he have been given instead, and was that what he got?",
        "Doxycycline 200 mg on day 1 then 100 mg once daily, orally. Yes: after amoxicillin was stopped, doxycycline 200 mg was started on 11/11/2026 at 09:00.",
        [kf("antibiotic", "doxycycline"), kf("first dose", "200 mg"), kf("then", "100 mg"), kf("given", "11/11/2026")],
        [ev(ANTI, "Moderate CAP, severe penicillin allergy Doxycycline 200 mg on day 1, then 100 mg once daily oral"), ev(MARL, "Doxycycline 200 mg 11/11/2026 09:00 Nurse A. Roche")],
        type="multi_document", difficulty="medium", style="yes_no", domain="medication_safety", rule="Policy alternative for severe penicillin allergy",
        fmt="drug and dose | yes/no", modes=["multi_document_join", "table_in_protocol"], skills=["table_lookup"], safety=True)
    follow_up(q4, "drill_down", "Who identified the problem with Yves Lefebvre's amoxicillin and when, according to the e-mail on file?", "Who spotted it?",
        "The ward pharmacist, Élodie Faure, during the chart review on the morning of 11/11/2026: she stopped amoxicillin, recommended doxycycline, asked for the drug chart to be corrected and filed an incident report (e-mail sent at 07:41).",
        [kf("who", "Faure"), kf("date", "11/11/2026"), kf("role", "pharmacist")],
        [ev(EML_L, "I stopped amoxicillin for Mr Lefebvre (MRN 4483391) and recommended doxycycline.")],
        type="direct", difficulty="easy", style="lookup", domain="medication_safety", rule="Who detected the conflict", fmt="name, role, date", modes=["email_source"], skills=["extraction"])

    # ---------------------------------------------------------------- 5. interactions (Coste)
    CH, BUL = "MAR_Coste_Raymond_2026-11-15", "PHA-INT-05_Drug_Interaction_Bulletin_Q4-2026"
    assert [(a, b) for a, b, *_ in S.coste_major_pairs()] == [("Simvastatin", "Clarithromycin"), ("Digoxin", "Clarithromycin")]
    q5 = main_q(5,
        "Using the drug chart of Raymond Coste (MRN 4469047) printed on 15/11/2026 and the pharmacy interaction bulletin PHA-INT-05, which pairs of his ACTIVE medicines are rated Major? "
        "Ignore discontinued prescriptions. Give the two medicines of each pair.",
        "Any major drug interactions on Mr Coste's current chart?",
        "Two Major pairs among his active medicines: simvastatin with clarithromycin, and digoxin with clarithromycin. The warfarin-clarithromycin pair, also rated Major, does not apply because warfarin was stopped on 10/11/2026.",
        [kf("pair 1", "simvastatin"), kf("pair 2", "digoxin"), kf("common drug", "clarithromycin"), kf("number of pairs", "Two", "2")],
        [ev(CH, "Simvastatin 40 mg at night ACTIVE"), ev(CH, "Clarithromycin 500 mg twice daily (started 13/11/2026, 7 days) ACTIVE"), ev(CH, "Digoxin 125 micrograms once daily ACTIVE"),
         ev(CH, "Warfarin 3 mg once daily STOPPED 10/11/2026"), ev(BUL, "Simvastatin Clarithromycin Major"), ev(BUL, "Digoxin Clarithromycin Major")],
        type="multi_document", difficulty="medium", style="list", domain="medication_safety", rule="Major interaction pairs among active medicines", safety=True,
        fmt="list of pairs", modes=["decoy_discontinued_drug", "table_in_protocol", "multi_document_join"], skills=["pair_enumeration", "filtering"])
    follow_up(q5, "next_step", "What does bulletin PHA-INT-05 recommend for each of the two Major pairs found on Raymond Coste's chart?", "What does it say to do about them?",
        "Simvastatin with clarithromycin: suspend simvastatin for the whole clarithromycin course. Digoxin with clarithromycin: avoid; if the combination is essential, halve the digoxin dose and check the digoxin level on day 3.",
        [kf("simvastatin action", "suspend simvastatin"), kf("digoxin action", "halve"), kf("level check", "day 3")],
        [ev(BUL, "Simvastatin Clarithromycin Major raised simvastatin exposure: myopathy / rhabdomyolysis suspend simvastatin for the whole clarithromycin course"),
         ev(BUL, "Digoxin Clarithromycin Major raised digoxin level: toxicity avoid; if essential halve the digoxin dose and check the level on day 3")],
        type="multi_evidence", difficulty="easy", style="list", domain="medication_safety", rule="Management of a Major interaction", fmt="one action per pair",
        modes=["table_in_protocol"], skills=["extraction"], safety=True)
    follow_up(q5, "scope_change", "Among Raymond Coste's active medicines, which pairs are rated Moderate in the bulletin, and what does it advise for each?", "And the moderate ones?",
        "Two Moderate pairs: ramipril with spironolactone (hyperkalaemia): check potassium and creatinine at 1 week; amlodipine with simvastatin (raised simvastatin exposure): limit simvastatin to 20 mg daily.",
        [kf("pair 1", "ramipril"), kf("pair 1 action", "1 week"), kf("pair 2", "amlodipine"), kf("pair 2 action", "20 mg")],
        [ev(BUL, "Ramipril Spironolactone Moderate hyperkalaemia check potassium and creatinine at 1 week"), ev(BUL, "Amlodipine Simvastatin Moderate raised simvastatin exposure limit simvastatin to 20 mg daily")],
        type="multi_evidence", difficulty="medium", style="list", domain="medication_safety", rule="Moderate interaction pairs among active medicines", fmt="pairs with advice",
        modes=["table_in_protocol", "decoy_discontinued_drug"], skills=["pair_enumeration", "filtering"])

    # ---------------------------------------------------------------- 6. warfarin (Perrin)
    INR, WAR = "INR_Perrin_Josiane_2026-11-10", "PHA-ANC-03_Warfarin_Dosing_Nomogram_v3"
    w1, w2 = S.warfarin_plan(3.4, D(2026, 11, 10)), S.warfarin_plan(4.3, D(2026, 11, 10))
    assert (w1["new_weekly"], w1["recheck"]) == (25.2, D(2026, 11, 17)) and (w2["new_weekly"], w2["recheck"]) == (23.8, D(2026, 11, 13))
    q6 = main_q(6,
        "Josiane Perrin (MRN 4472260) had an INR on 10/11/2026. Apply nomogram PHA-ANC-03: give the action, her new weekly warfarin dose in mg and the date of the next INR.",
        "What should Mrs Perrin's warfarin be after her INR on 10/11?",
        "INR 3.4 falls in the 3.1-3.9 row: decrease the weekly dose by 10%, from 28 mg to 25.2 mg per week. Next INR in 7 days, on 17/11/2026.",
        [kf("action", "decrease the weekly dose by 10%", "decrease weekly dose by 10%", "10%"), kf("new weekly dose", "25.2 mg", "25.2", "25,2"), kf("next INR", "17/11/2026")],
        [ev(INR, "Dose hebdomadaire actuelle 28 mg (4 mg par jour)"), ev(INR, "10/11/2026 3,4 28 mg"), ev(WAR, "3.1 to 3.9 decrease weekly dose by 10% in 7 days")],
        type="calculation", difficulty="medium", style="conditional", domain="pharmacy", rule="Warfarin maintenance nomogram", safety=True,
        fmt="action | new weekly dose | next INR date", modes=["french_document", "multi_document_join", "table_in_protocol", "derived_value"], skills=["table_lookup", "percentage_change", "date_arithmetic"],
        calculation=calc({"weekly": 28, "pct": 10}, "weekly * (1 - pct / 100)", 25.2, {"weekly": (0, "28", "mg", 1), "pct": (2, "10%", "%", 1)}))
    follow_up(q6, "hypothetical_variation", "If Josiane Perrin's INR on 10/11/2026 had been 4.3 instead, what would nomogram PHA-ANC-03 require (doses to omit, new weekly dose, next INR date)?",
        "What if it had been 4.3?",
        "INR 4.3 falls in the 4.0-4.9 row: omit one dose, then decrease the weekly dose by 15%, from 28 mg to 23.8 mg per week. Next INR in 3 days, on 13/11/2026.",
        [kf("doses to omit", "omit one dose", "one dose"), kf("new weekly dose", "23.8 mg", "23.8", "23,8"), kf("next INR", "13/11/2026")],
        [ev(INR, "Dose hebdomadaire actuelle 28 mg (4 mg par jour)"), ev(WAR, "4.0 to 4.9 omit one dose, then decrease weekly dose by 15% in 3 days")],
        type="calculation", difficulty="medium", style="conditional", domain="pharmacy", rule="Warfarin maintenance nomogram", safety=True,
        fmt="action | new weekly dose | next INR date", modes=["french_document", "hypothetical_variation", "table_in_protocol"], skills=["table_lookup", "percentage_change", "date_arithmetic"],
        calculation=calc({"weekly": 28, "pct": 15}, "weekly * (1 - pct / 100)", 23.8, {"weekly": (0, "28", "mg", 1), "pct": (1, "15%", "%", 1)}))
    follow_up(q6, "compare_over_time", "Were Josiane Perrin's two previous INR values (27/10/2026 and 03/11/2026) within her target range?", "Was she in range before that?",
        "Yes. Her INR was 2.4 on 27/10/2026 and 2.6 on 03/11/2026, both within the target range of 2.0 to 3.0.",
        [kf("INR 27/10", "2.4", "2,4"), kf("INR 03/11", "2.6", "2,6"), kf("target", "2.0 to 3.0", "2,0 - 3,0", "2.0 - 3.0", "2.0-3.0", "2,0-3,0")],
        [ev(INR, "27/10/2026 2,4 28 mg"), ev(INR, "03/11/2026 2,6 28 mg"), ev(INR, "INR cible 2,0 - 3,0")],
        type="temporal", difficulty="easy", style="yes_no", domain="pharmacy", rule="INR history against the target", fmt="yes/no with values", modes=["french_document", "same_analyte_multiple_dates"], skills=["interval_comparison"])

    # ---------------------------------------------------------------- 7. vaccination (Blanc)
    VAC, SCH = "VAC_Blanc_Gerard_2026-11-20", "IMM-SCH-01_Calendrier_vaccinal_adulte_v2"
    st = S.blanc_status()
    assert st["tdap_due"] == D(2025, 3, 12) and st["rzv_window"] == (D(2026, 7, 5), D(2026, 11, 5))
    q7 = main_q(7,
        "On 20/11/2026, what is the status of each vaccine in schedule IMM-SCH-01 for Gérard Blanc (MRN 4490518, born 18/03/1959)? Classify each as up to date, due (never given, or the current season not covered) "
        "or overdue (due date passed), and give the due date for those that are overdue.",
        "Is Mr Blanc up to date with his vaccines?",
        "dTcaP: overdue, the booster was due on 12/03/2025 (10 years after 12/03/2015). Seasonal influenza: due, his last dose (14/10/2025) covered the 2025-26 season and the 2026-27 season started on 15/10/2026. "
        "Pneumococcal PCV20: due, never given (he is over 65). Zoster (RZV): overdue, dose 2 was due between 05/07/2026 and 05/11/2026 (2 to 6 months after dose 1 on 05/05/2026); give it as soon as possible without restarting. "
        "COVID-19: up to date (autumn 2026 dose given 20/10/2026).",
        [kf("dTcaP due date", "12/03/2025"), kf("zoster window end", "05/11/2026"), kf("influenza", "due"), kf("PCV20", "never given", "not given", "never"), kf("COVID-19", "up to date")],
        [ev(VAC, "dTcaP (tetanus-diphtheria-pertussis) 12/03/2015"), ev(VAC, "Influenza 2025-26 14/10/2025"), ev(VAC, "Zoster recombinant (RZV) dose 1 05/05/2026"), ev(VAC, "COVID-19 autumn 2026 20/10/2026"),
         ev(SCH, "rappel tous les 10 ans"), ev(SCH, "une dose chaque saison, à partir du 15 octobre"), ev(SCH, "2 doses espacées de 2 à 6 mois")],
        type="multi_document", difficulty="hard", style="list", domain="preventive_care", rule="Adult immunisation schedule applied to a vaccination record", safety=False,
        fmt="table: vaccine | status | due date", modes=["french_document", "multi_document_join", "derived_value", "absence_of_document"], skills=["date_arithmetic", "rule_application", "absence_reasoning"])
    follow_up(q7, "drill_down", "By what date should Gérard Blanc's tetanus booster have been given?", "When was his tetanus booster due?",
        "By 12/03/2025: the schedule requires a booster 10 years after the last dose, which was given on 12/03/2015.",
        [kf("due date", "12/03/2025"), kf("last dose", "12/03/2015")], [ev(VAC, "dTcaP (tetanus-diphtheria-pertussis) 12/03/2015"), ev(SCH, "rappel tous les 10 ans")],
        type="temporal", difficulty="easy", style="lookup", domain="preventive_care", rule="Booster interval", fmt="one date", modes=["french_document", "derived_value"], skills=["date_arithmetic"])
    follow_up(q7, "next_step", "What is the window for Gérard Blanc's second zoster dose, has it closed, and what does the schedule say to do?", "And the shingles second dose, what's the situation?",
        "The window runs from 05/07/2026 to 05/11/2026 (2 to 6 months after dose 1 on 05/05/2026). It closed on 05/11/2026. The schedule says to give the second dose as soon as possible without restarting the course.",
        [kf("window start", "05/07/2026"), kf("window end", "05/11/2026"), kf("action", "as soon as possible", "dès que possible"), kf("restart", "without restarting", "not restart", "no restart", "sans reprendre")],
        [ev(VAC, "Zoster recombinant (RZV) dose 1 05/05/2026"), ev(SCH, "2 doses espacées de 2 à 6 mois ; si l'intervalle de 6 mois est dépassé, administrer la … seconde dose dès que possible sans reprendre le schéma")],
        type="temporal", difficulty="medium", style="conditional", domain="preventive_care", rule="Zoster dose-2 interval rules", fmt="window | closed? | action", modes=["french_document", "derived_value"], skills=["date_arithmetic", "rule_application"])

    # ---------------------------------------------------------------- 8. nodule (Roussel)
    CT1, CT2, NOD = "CT_Chest_Roussel_Simone_2026-03-14", "CT_Chest_Roussel_Simone_2026-11-12", "RAD-FUP-02_Pulmonary_Nodule_Follow-up_Guideline_v2"
    q8 = main_q(8,
        "Compare the right upper lobe nodule in Simone Roussel's (MRN 4465730) CT chest reports of 14/03/2026 and 12/11/2026. Give the percentage change in longest diameter, "
        "and the action and deadline required by guideline RAD-FUP-02.",
        "Has Mrs Roussel's lung nodule grown, and what do we have to do?",
        "The right upper lobe nodule grew from 9 mm to 12 mm: +33.3% in longest diameter, which is above the 20% threshold. The guideline requires referral to the thoracic MDT within 14 days of the report date (12/11/2026), "
        "i.e. by 26/11/2026, with a PET-CT before the MDT. The 4 mm left lower lobe nodule is stable and needs no action.",
        [kf("change", "33.3%", "33%", "33.33%"), kf("action", "MDT", "multidisciplinary"), kf("deadline", "26/11/2026"), kf("imaging", "PET-CT")],
        [ev(CT1, "Solid nodule of the right upper lobe, longest axial diameter 9 mm"), ev(CT2, "Solid nodule of the right upper lobe, longest axial diameter 12 mm"),
         ev(NOD, "Known nodule, increase in longest diameter of 20% or more refer to the thoracic multidisciplinary team (MDT) within 14 days of the report date; PET-CT before the MDT")],
        type="calculation", difficulty="medium", style="conditional", domain="imaging", rule="Nodule growth threshold and MDT deadline", safety=True,
        fmt="percentage change | action | deadline", modes=["multi_document_join", "same_analyte_multiple_dates", "derived_value"], skills=["percentage_change", "date_arithmetic", "table_lookup"],
        calculation=calc({"prev_mm": 9, "now_mm": 12}, "(now_mm - prev_mm) / prev_mm * 100", S.nodule_growth_pct(), {"prev_mm": (0, "9", "mm", 1), "now_mm": (1, "12", "mm", 1)}))
    follow_up(q8, "hypothetical_variation", "If the right upper lobe nodule had measured 10 mm on 12/11/2026 instead of 12 mm, what would guideline RAD-FUP-02 require and by when?", "And if it had been 10 mm?",
        "From 9 mm to 10 mm is +11.1%, below 20%: repeat CT 12 months after the latest examination, i.e. on 12/11/2027. No MDT referral.",
        [kf("change", "11.1%", "11%", "11.11%"), kf("action", "repeat CT", "CT"), kf("date", "12/11/2027", "12 months")],
        [ev(CT1, "Solid nodule of the right upper lobe, longest axial diameter 9 mm"), ev(NOD, "Known nodule, increase in longest diameter under 20% repeat CT 12 months after the latest examination")],
        type="multi_evidence", difficulty="medium", style="conditional", domain="imaging", rule="Nodule growth threshold", safety=False, fmt="percentage change | action | date",
        modes=["hypothetical_variation", "table_in_protocol", "derived_value"], skills=["percentage_change", "date_arithmetic"])
    follow_up(q8, "scope_change", "Does the 4 mm left lower lobe nodule in Simone Roussel's latest CT need any follow-up under the guideline? No risk factor is documented for her.", "What about the small one on the other side?",
        "No. The 4 mm left lower lobe nodule is unchanged from previous imaging and is under 6 mm: the guideline requires no follow-up for a solid nodule under 6 mm with no risk factor.",
        [kf("answer", "no follow-up", "no action", "none"), kf("size", "4 mm")],
        [ev(CT2, "A second solid nodule of the left lower lobe measures 4 mm and is unchanged from previous imaging"), ev(NOD, "Solid nodule under 6 mm, no risk factor no follow-up")],
        type="multi_document", difficulty="easy", style="yes_no", domain="imaging", rule="Small nodule without follow-up", fmt="yes/no with reason", modes=["multi_document_join"], skills=["table_lookup"])

    # ---------------------------------------------------------------- 9. surgical prophylaxis (Tessier)
    AN, OP = "ANAES_Tessier_Bernard_2026-11-17", "OPNOTE_Tessier_Bernard_2026-11-17"
    t = S.TESSIER
    assert S.minutes_between(t["given"], t["incision"]) == 31 and S.prophylaxis_required_dose(t["weight"]) == 3
    q9 = main_q(9,
        "For Bernard Tessier's (MRN 4487715) laparoscopic cholecystectomy on 17/11/2026, was the surgical antibiotic prophylaxis compliant with policy PHA-ANT-01 for the dose and for the timing? "
        "Give the agent, the dose given, the time given, the time of incision and the interval in minutes.",
        "Was Mr Tessier's antibiotic prophylaxis given correctly before his gallbladder operation?",
        "Not fully. Cefazolin 2 g IV was given at 08:21 and the skin incision was at 08:52: an interval of 31 minutes, so the timing complies (within 60 minutes). "
        "The dose does not: at 124 kg (120 kg or more) the policy requires 3 g, so 2 g was 1 g short.",
        [kf("agent", "cefazolin"), kf("dose given", "2 g"), kf("required dose", "3 g"), kf("interval", "31 minutes", "31 min"), kf("weight", "124 kg"), kf("timing", "within 60 minutes", "compliant")],
        [ev(AN, "08:21 Cefazolin 2 g intravenous"), ev(AN, "08:52 Skin incision"), ev(AN, "Weight / height 124 kg / 181 cm"), ev(ANTI, "Dose 2 g; 3 g if body weight is 120 kg or more"),
         ev(ANTI, "Timing within 60 minutes before skin incision")],
        type="multi_document", difficulty="hard", style="yes_no", domain="surgery", rule="Surgical prophylaxis dose by weight and timing before incision", safety=True,
        fmt="dose: compliant? | timing: compliant? | values", modes=["multi_document_join", "table_in_protocol", "threshold_boundary"], skills=["time_arithmetic", "threshold_comparison"])
    follow_up(q9, "scope_change", "Did Bernard Tessier's operation of 17/11/2026 require a re-dose of the prophylactic antibiotic according to policy PHA-ANT-01?", "Did he need a second dose during the operation?",
        "No. A re-dose is required if the operation lasts more than 4 hours or blood loss exceeds 1,500 mL. The operation ran from 08:52 to 09:48 (56 minutes) with an estimated blood loss of 50 mL.",
        [kf("re-dose", "no", "not required"), kf("duration", "56 minutes", "56 min"), kf("blood loss", "50 mL")],
        [ev(ANTI, "Re-dosing repeat the dose if the operation lasts more than 4 hours or blood loss exceeds 1,500 mL"), ev(AN, "08:52 Skin incision"), ev(AN, "09:48 End of surgery"), ev(AN, "Estimated blood loss 50 mL")],
        type="multi_document", difficulty="medium", style="yes_no", domain="surgery", rule="Surgical prophylaxis re-dosing", fmt="yes/no with figures", modes=["multi_document_join", "table_in_protocol"], skills=["time_arithmetic", "threshold_comparison"])
    follow_up(q9, "scope_change", "Is any post-operative antibiotic continuation required for this operation under policy PHA-ANT-01?", "Does he need antibiotics after the operation?",
        "No. For clean-contaminated cases the policy requires a single dose and no post-operative continuation.",
        [kf("answer", "no", "single dose"), kf("duration", "single dose")], [ev(ANTI, "Duration single dose; no post-operative continuation for clean-contaminated cases")],
        type="direct", difficulty="easy", style="yes_no", domain="surgery", rule="Surgical prophylaxis duration", fmt="yes/no", modes=["table_in_protocol"], skills=["extraction"])

    # ---------------------------------------------------------------- 10. paediatric paracetamol (Moreau)
    PM, PH = "PRESC_Moreau_Lea_2026-11-16", "PAE-DOS-01_Paediatric_Dosing_Handbook_2026"
    lim = S.paed_limits()
    assert (lim["single"], lim["daily"], lim["ml"]) == (217.5, 870.0, 9.0)
    q10 = main_q(10,
        "Check Léa Moreau's (MRN 4492206) paracetamol prescription of 16/11/2026 against the Paediatric Dosing Handbook. Give the maximum single dose and the maximum daily dose in mg for her measured weight, "
        "the daily dose actually prescribed, and say whether the prescription is within the limits.",
        "Is the paracetamol dose for little Léa Moreau safe?",
        "Weight 14.5 kg: maximum single dose 15 mg/kg = 217.5 mg; maximum daily dose 60 mg/kg = 870 mg. The prescription is 500 mg every 6 hours = 2,000 mg per day, "
        "so it exceeds both limits (the single dose is 2.3 times the maximum) and must not be dispensed. The handbook's 1 g cap on a single dose does not bind at this weight.",
        [kf("max single dose", "217.5 mg", "217,5"), kf("max daily dose", "870 mg"), kf("prescribed daily", "2,000 mg", "2000 mg", "2 000 mg"), kf("prescribed single", "500 mg"), kf("verdict", "exceeds", "not within", "above")],
        [ev(PM, "Poids mesuré 14,5 kg"), ev(PM, "Paracétamol suspension buvable 500 mg PO toutes les 6 heures"), ev(PH, "Single dose 15 mg/kg per dose"), ev(PH, "Maximum daily dose 60 mg/kg per 24 hours, not exceeding 4 g")],
        type="calculation", difficulty="medium", style="yes_no", domain="pharmacy", rule="Paediatric weight-based paracetamol limits", safety=True, fmt="max single | max daily | prescribed | verdict",
        modes=["french_document", "multi_document_join", "derived_value"], skills=["unit_arithmetic", "threshold_comparison"],
        calculation=calc({"weight_kg": 14.5, "mg_per_kg": 15}, "weight_kg * mg_per_kg", 217.5, {"weight_kg": (0, "14,5", "kg", 1), "mg_per_kg": (2, "15", "mg/kg", 1)}))
    follow_up(q10, "calculation", "What volume of the paracetamol oral suspension (120 mg in 5 mL) corresponds to Léa Moreau's maximum single dose, using the handbook's rounding rule?", "How many mL is that maximum dose?",
        "217.5 mg / 24 mg per mL = 9.06 mL, rounded down to the nearest 0.5 mL: 9.0 mL.",
        [kf("volume", "9.0 mL", "9 mL", "9,0 mL"), kf("concentration", "24 mg per mL", "24 mg/mL", "120 mg in 5 mL")],
        [ev(PM, "Poids mesuré 14,5 kg"), ev(PH, "Single dose 15 mg/kg per dose"), ev(PH, "Oral suspension 120 mg in 5 mL (24 mg/mL)"), ev(PH, "Volumes are rounded down to the nearest 0.5 mL")],
        type="calculation", difficulty="medium", style="lookup", domain="pharmacy", rule="Volume of oral suspension, rounded down to 0.5 mL", safety=True, fmt="volume in mL",
        modes=["french_document", "unit_conversion", "derived_value"], skills=["unit_arithmetic", "rounding_rule"],
        calculation=calc({"weight_kg": 14.5, "mg_per_kg": 15, "mg_per_ml": 24}, "weight_kg * mg_per_kg / mg_per_ml", lim["ml_raw"], {"weight_kg": (0, "14,5", "kg", 1), "mg_per_kg": (1, "15", "mg/kg", 1), "mg_per_ml": (2, "24", "mg/mL", 1)}))
    follow_up(q10, "calculation", "How many times the maximum single dose is the 500 mg dose prescribed for Léa Moreau?", "So how much over the limit is it?",
        "500 mg / 217.5 mg = 2.3 times the maximum single dose.",
        [kf("ratio", "2.3", "2,3")],
        [ev(PM, "Poids mesuré 14,5 kg"), ev(PM, "Paracétamol suspension buvable 500 mg PO toutes les 6 heures"), ev(PH, "Single dose 15 mg/kg per dose")],
        type="calculation", difficulty="easy", style="comparison", domain="pharmacy", rule="Prescribed dose against the maximum", safety=True, fmt="one ratio",
        modes=["french_document", "derived_value"], skills=["unit_arithmetic"],
        calculation=calc({"prescribed_mg": 500, "weight_kg": 14.5, "mg_per_kg": 15}, "prescribed_mg / (weight_kg * mg_per_kg)", 500 / 217.5,
                         {"prescribed_mg": (1, "500", "mg", 1), "weight_kg": (0, "14,5", "kg", 1), "mg_per_kg": (2, "15", "mg/kg", 1)}))

    # ---------------------------------------------------------------- 11. identity mismatch (Girard / Giraud)
    AG, LG16, LG15, AGI = "ADM_Girard_Henri_2026-11-12", "LAB_Girard_Henri_2026-11-16", "LAB_Girard_Henri_2026-11-15", "ADM_Giraud_Henri_2026-11-13"
    q11 = main_q(11,
        "Is the laboratory report dated 16/11/2026 that is filed under the name Henri Girard really that patient's? Compare the name, date of birth, MRN and ward printed on the report with Henri Girard's admission note.",
        "Is the 16/11 lab result in Henri Girard's file actually his?",
        "No. The admission note identifies GIRARD Henri, born 14/03/1951, MRN 5502144, Medicine 3B. The report of 16/11/2026 is headed GIRAUD Henri, born 14/03/1957, MRN 5502414, Medicine 3A: "
        "the surname, date of birth, MRN and ward all differ. It belongs to another patient and has been misfiled.",
        [kf("Girard MRN", "5502144"), kf("report MRN", "5502414"), kf("Girard DOB", "14/03/1951"), kf("report DOB", "14/03/1957"), kf("verdict", "No", "not his", "not the same patient", "different patient")],
        [ev(AG, "Date of birth / sex 14/03/1951 / M"), ev(AG, "MRN 5502144"), ev(LG16, "Date of birth / sex 14/03/1957 / M"), ev(LG16, "MRN 5502414"), ev(LG16, "GIRAUD Henri | DOB 14/03/1957 (M) | MRN 5502414 | Medicine 3A")],
        type="multi_document", difficulty="hard", style="yes_no", domain="patient_identification", rule="Patient identifiers on a filed document", safety=True, fmt="yes/no | identifiers compared",
        modes=["similar_patient_names", "multi_document_join", "terminology_mismatch"], skills=["identifier_comparison"])
    follow_up(q11, "drill_down", "Whose report is it, and what critical value does it contain?", "So who does it belong to, and is anything critical?",
        "It belongs to Henri GIRAUD (MRN 5502414, born 14/03/1957, Medicine 3A), whose own admission note is dated 13/11/2026. It contains a critical potassium of 6.1 mmol/L, telephoned to the ward on 16/11/2026 at 10:42.",
        [kf("patient", "Giraud"), kf("MRN", "5502414"), kf("critical potassium", "6.1"), kf("time of call", "10:42")],
        [ev(LG16, "CRITICAL VALUE: potassium 6.1 mmol/L telephoned to the ward on 16/11/2026 at 10:42."), ev(AGI, "MRN 5502414")],
        type="multi_document", difficulty="medium", style="lookup", domain="patient_identification", rule="Identify the true owner of a misfiled report", safety=True, fmt="patient | critical value",
        modes=["similar_patient_names", "multi_document_join"], skills=["identifier_comparison", "extraction"])
    follow_up(q11, "scope_change", "Does Henri Girard (MRN 5502144) have any valid laboratory report for 16/11/2026? If not, what is his most recent valid creatinine?", "So does Henri Girard have a valid result for the 16th?",
        "No: the only report filed for 16/11/2026 belongs to another patient. His most recent valid report is that of 15/11/2026, with a creatinine of 148 µmol/L (potassium 4.7 mmol/L).",
        [kf("valid report 16/11", "no", "none"), kf("latest valid date", "15/11/2026"), kf("creatinine", "148")],
        [ev(LG15, "Creatinine 148 µmol/L 60 - 110 H"), ev(LG15, "Potassium 4.7 mmol/L 3.5 - 5.0")],
        type="multi_evidence", difficulty="medium", style="yes_no", domain="patient_identification", rule="Most recent valid result after a misfiled report", safety=True, fmt="yes/no | latest value",
        modes=["similar_patient_names", "absence_of_document", "same_analyte_multiple_dates"], skills=["absence_reasoning"])

    # ---------------------------------------------------------------- 12. consent (Robert)
    CON, CRO, LEG = "SCAN_20261118_0802", "CRO_Robert_Michel_2026-11-18", "LEG-CON-01_Consent_to_Treatment_Policy_v4"
    q12 = main_q(12,
        "Does the consent form signed by Michel Robert (MRN 4488023) on 18/11/2026 match the operation actually performed that day? Compare the procedure, the side and the timing "
        "(policy LEG-CON-01 requires signature before any pre-medication).",
        "Does Mr Robert's consent form match the operation he had?",
        "No. The timing is valid: the patient signed at 07:45, before the pre-medication at 08:30. But the side is wrong: the consent is for an arthroscopy of the RIGHT knee whereas the operation note records an arthroscopy of the LEFT knee (site marked left).",
        [kf("consent side", "right", "droit"), kf("operated side", "left", "gauche"), kf("patient signature", "07:45"), kf("pre-medication", "08:30"), kf("verdict", "No", "does not match", "mismatch")],
        [ev(CON, "Intervention proposée Arthroscopie du genou DROIT"), ev(CON, "Signature du patient Michel Robert - signé le 18/11/2026 à 07:45"), ev(CRO, "Arthroscopie du genou GAUCHE avec méniscectomie partielle interne"),
         ev(CRO, "Prémédication administrée 08:30"), ev(LEG, "The patient signs the form before any pre-medication is given")],
        type="multi_document", difficulty="hard", style="yes_no", domain="consent", rule="Consent matches procedure, side and timing", safety=True, fmt="match? | procedure | side | timing",
        modes=["scanned_document", "french_document", "multi_document_join", "terminology_mismatch"], skills=["laterality_check", "time_comparison"])
    follow_up(q12, "next_step", "What does the consent policy require when the side on the consent form differs from the operative site?", "What are we supposed to do in that situation?",
        "The operation must not proceed. The surgeon stops the line, the team confirms the site with the patient, a new consent form is completed and the discrepancy is reported in the incident reporting system within 24 hours.",
        [kf("rule", "must not proceed", "not proceed"), kf("new form", "new consent"), kf("report", "24 hours")],
        [ev(LEG, "If the procedure or the side on the consent form differs from the planned or marked operative site, the operation must not proceed.")],
        type="direct", difficulty="easy", style="explanatory", domain="consent", rule="Discrepancy at the time of surgery", fmt="short procedure", modes=["table_in_protocol"], skills=["extraction"], safety=True)
    follow_up(q12, "drill_down", "Who signed Michel Robert's consent form as surgeon, and at what time?", "Who signed for the surgeon, and when?",
        "Dr Anselme Vidal signed as surgeon on 18/11/2026 at 07:50.",
        [kf("surgeon", "Vidal"), kf("time", "07:50")], [ev(CON, "Signature du chirurgien Dr A. Vidal - signé le 18/11/2026 à 07:50")],
        type="direct", difficulty="easy", style="lookup", domain="consent", rule="Surgeon's signature", fmt="name and time", modes=["scanned_document", "french_document"], skills=["extraction"])

    # ---------------------------------------------------------------- 13. IV antibiotic duration (Guérin)
    MG = "MAR_Guerin_Anne-Sophie_2026-11-03"
    assert len(S.GUERIN_DOSES) == 7 and len(S.guerin_given()) == 6
    q13 = main_q(13,
        "How many doses of intravenous ceftriaxone were actually administered to Anne-Sophie Guérin (MRN 4491174) between 03/11/2026 and 09/11/2026, and how many of them were given after the 3-day limit "
        "on intravenous therapy for community-acquired pneumonia in policy PHA-ANT-01 (day 1 = 03/11/2026)? Give the dates.",
        "How many IV antibiotic doses did Mrs Guérin really get, and was it too long?",
        "Six doses were administered (03, 04, 05, 07, 08 and 09/11/2026); the 06/11/2026 dose was not given. The policy limits IV therapy to 3 days (03-05/11/2026), "
        "so three doses were given beyond the limit: 07/11/2026, 08/11/2026 and 09/11/2026.",
        [kf("doses administered", "Six", "6"), kf("doses beyond limit", "three", "3"), kf("first excess dose", "07/11/2026", "07/11"), kf("last dose", "09/11/2026"), kf("limit", "3 days", "three days")],
        [ev(MG, "03/11/2026 18:00 G A. Dubois"), ev(MG, "06/11/2026 18:00 N"), ev(MG, "09/11/2026 18:00 G A. Dubois"), ev(ANTI, "Intravenous therapy is limited to 3 days")],
        type="multi_document", difficulty="hard", style="count", domain="antimicrobial_stewardship", rule="IV antibiotic duration against the policy limit", safety=True,
        fmt="doses administered | doses beyond the limit | dates", modes=["decoy_not_given_dose", "multi_document_join", "derived_value"], skills=["counting", "date_arithmetic", "threshold_comparison"])
    follow_up(q13, "drill_down", "Which ceftriaxone dose was not given to Anne-Sophie Guérin, and why?", "Which dose was missed?",
        "The dose of 06/11/2026 at 18:00 was not given (code N): the patient was off the ward for a CT scan at the scheduled time.",
        [kf("date", "06/11/2026"), kf("reason", "CT scan", "CT")], [ev(MG, "06/11/2026 18:00 N - patient off ward for CT scan at scheduled time")],
        type="direct", difficulty="easy", style="lookup", domain="antimicrobial_stewardship", rule="Reason for a missed dose", fmt="date and reason", modes=["decoy_not_given_dose"], skills=["extraction"])
    follow_up(q13, "next_step", "From which date should Anne-Sophie Guérin have been switched to oral therapy under policy PHA-ANT-01, and with what regimen (no allergy is recorded)?", "When should she have gone onto tablets, and which?",
        "From day 4, i.e. 06/11/2026, she should have been switched to the oral regimen: amoxicillin 1 g three times daily (no allergy is recorded), unless the infectious diseases team documented a reason to continue IV therapy; none is documented.",
        [kf("switch date", "06/11/2026"), kf("regimen", "amoxicillin"), kf("dose", "1 g")],
        [ev(ANTI, "from day 4 the patient must be switched to the oral regimen"), ev(ANTI, "Moderate CAP, no allergy Amoxicillin 1 g three times daily oral"), ev(MG, "Allergies none known")],
        type="multi_document", difficulty="medium", style="conditional", domain="antimicrobial_stewardship", rule="IV to oral switch from day 4", fmt="date | regimen", modes=["multi_document_join", "derived_value"], skills=["date_arithmetic", "table_lookup"])

    # ---------------------------------------------------------------- 14. pending results (Benali)
    CRB, LB, MB, DIS = "CRH_Benali_Nadia_2026-11-12", "LAB_Benali_Nadia_2026-11-13", "MICRO_Benali_Nadia_2026-11-17", "ADM-DIS-04_Discharge_and_Transfer_of_Care_Policy_v3"
    q14 = main_q(14,
        "Which results were pending when Nadia Benali (MRN 4474409) was discharged on 12/11/2026? For each, give the final value or outcome and the date it was finalised.",
        "What was still pending when Mrs Benali went home, and what came back?",
        "Three results were pending: blood culture set 2 (no growth at 5 days, final report 17/11/2026), TSH (9.80 mIU/L, high, reference 0.40-4.00, final 13/11/2026) and 25-OH vitamin D (38 nmol/L, low, reference 50-125, final 13/11/2026).",
        [kf("TSH", "9.80", "9.8"), kf("vitamin D", "38"), kf("blood culture", "no growth"), kf("TSH final date", "13/11/2026"), kf("culture final date", "17/11/2026")],
        [ev(CRB, "Blood culture, set 2 11/11/2026"), ev(CRB, "TSH 11/11/2026"), ev(CRB, "25-OH vitamin D 11/11/2026"), ev(LB, "TSH 9.80 mIU/L 0.40 - 4.00 H"), ev(LB, "25-OH vitamin D 38 nmol/L 50 - 125 L"),
         ev(MB, "Blood culture, set 2 no growth at 5 days")],
        type="multi_document", difficulty="medium", style="list", domain="care_transition", rule="Results pending at discharge and their outcome", safety=True, fmt="table: test | result | final date",
        modes=["multi_document_join", "same_analyte_multiple_dates"], skills=["multi_document_join"])
    follow_up(q14, "next_step", "By which date must the abnormal results of Nadia Benali be communicated to her GP under the discharge policy ADM-DIS-04?", "When does the GP have to be told?",
        "The abnormal results (TSH and vitamin D) were finalised on Friday 13/11/2026. The policy requires communication to the GP within 2 working days of finalisation: by Tuesday 17/11/2026. The blood culture is normal and is filed without communication.",
        [kf("deadline", "17/11/2026"), kf("rule", "2 working days", "two working days"), kf("blood culture", "without communication", "no communication", "normal")],
        [ev(DIS, "Every abnormal result finalised after discharge is communicated to the GP within 2 working days of the date the result is finalised."), ev(LB, "Final report issued 13/11/2026")],
        type="temporal", difficulty="medium", style="conditional", domain="care_transition", rule="GP communication within 2 working days", safety=True, fmt="date",
        modes=["multi_document_join", "derived_value"], skills=["business_day_arithmetic"])
    follow_up(q14, "drill_down", "Who remains responsible for acting on Nadia Benali's pending results, and who is her GP?", "Who is responsible for following those up, and who's the GP?",
        "The discharging consultant, Dr Hélène Roux, remains responsible for the pending results. The GP is Dr Pascal Garnier.",
        [kf("responsible", "Roux"), kf("general practitioner", "Garnier")],
        [ev(CRB, "Consultant Dr Hélène Roux"), ev(CRB, "GP Dr Pascal Garnier"), ev(DIS, "The consultant who discharged the patient remains responsible for results pending at discharge.")],
        type="multi_document", difficulty="easy", style="lookup", domain="care_transition", rule="Responsibility for pending results", fmt="two names", modes=["multi_document_join"], skills=["extraction"])

    # ---------------------------------------------------------------- 15. follow-up appointments (Martel)
    CRM, BK = "CRH_Martel_Jacques_2026-11-06", "Clinic_Bookings_Export_2026-11-19"
    stt = S.martel_status()
    assert [x[3] for x in stt] == [12, -9, None]
    q15 = main_q(15,
        "List the follow-up arrangements requested in Jacques Martel's (MRN 4468815) discharge summary (discharged 06/11/2026) and the latest date each should take place. Then, using the bookings export of 19/11/2026, "
        "say which are booked and whether each booking meets its timeframe.",
        "Are Mr Martel's follow-up appointments booked in time?",
        "Cardiology clinic (within 14 days): due by 20/11/2026, booked 02/12/2026 at 10:20, which is 12 days late. Cardiac rehabilitation assessment (within 28 days): due by 04/12/2026, booked 25/11/2026: compliant. "
        "Transthoracic echocardiogram (at 6 weeks): due by 18/12/2026, no booking found in the export.",
        [kf("cardiology deadline", "20/11/2026"), kf("cardiology booking", "02/12/2026"), kf("rehab deadline", "04/12/2026"), kf("rehab booking", "25/11/2026"), kf("echo deadline", "18/12/2026"),
         kf("echo status", "no booking", "not booked", "no appointment", "none")],
        [ev(CRM, "Cardiology clinic within 14 days"), ev(CRM, "Cardiac rehabilitation assessment within 28 days"), ev(CRM, "Transthoracic echocardiogram at 6 weeks"),
         ev(BK, "MARTEL Jacques 4468815 Cardiology clinic 02/12/2026 10:20"), ev(BK, "MARTEL Jacques 4468815 Cardiac rehabilitation assessment 25/11/2026 14:00")],
        type="multi_document", difficulty="hard", style="list", domain="care_transition", rule="Follow-up requested at discharge against bookings", safety=True,
        fmt="table: follow-up | due date | booked date | compliant?", modes=["multi_document_join", "absence_of_document", "derived_value", "deep_in_report"], skills=["date_arithmetic", "absence_reasoning"])
    follow_up(q15, "calculation", "By how many days does Jacques Martel's cardiology clinic booking miss the requested timeframe?", "How late is the cardiology appointment?",
        "12 days: the clinic was due within 14 days of 06/11/2026 (by 20/11/2026) and is booked on 02/12/2026.",
        [kf("days late", "12 days", "12")], [ev(CRM, "Cardiology clinic within 14 days"), ev(BK, "MARTEL Jacques 4468815 Cardiology clinic 02/12/2026 10:20")],
        type="temporal", difficulty="easy", style="lookup", domain="care_transition", rule="Days between deadline and booking", fmt="number of days", modes=["multi_document_join", "derived_value"], skills=["date_arithmetic"])
    follow_up(q15, "next_step", "According to policy ADM-DIS-04, what should happen when a follow-up booking is later than the timeframe requested on the discharge summary?", "What do we do about a late booking like that?",
        "The booking is escalated to the clinic manager.",
        [kf("action", "escalated to the clinic manager", "clinic manager")], [ev(DIS, "a booking later than the requested timeframe is escalated to the clinic manager")],
        type="direct", difficulty="easy", style="explanatory", domain="care_transition", rule="Escalation of late follow-up bookings", fmt="one sentence", modes=[], skills=["extraction"])

    # ---------------------------------------------------------------- 16. MRSA isolation (Ward 4B)
    W4, IPC = "IPC_MRSA_screening_Ward4B_2026-11-14", "IPC-MAN-01_Manuel_de_prevention_des_infections_v6"
    assert [r[0] for r in S.ward4b_needing_isolation_in_bay()] == ["4B-02", "4B-04", "4B-07"]
    q16 = main_q(16,
        "On Ward 4B at 14/11/2026, which patients should be in a single room with contact precautions according to IPC manual IPC-MAN-01 but are currently in a bay? Give bed, patient and reason.",
        "Who on Ward 4B should be isolated for MRSA but is sitting in a bay?",
        "Three patients: bed 4B-02 (Bernier, MRSA positive), bed 4B-07 (Gaillard, MRSA positive) and bed 4B-04 (Delmas, screen pending, transferred from another hospital: pre-emptive isolation applies). "
        "Not concerned: 4B-06 (positive but already in a single room), 4B-09 (pending, transfer, already in a single room), 4B-05 (pending, from home: standard precautions) and 4B-12 (transfer but negative).",
        [kf("bed", "4B-02"), kf("bed", "4B-04"), kf("bed", "4B-07")],
        [ev(W4, "4B-02 Bernier, T. Care home Bay Positive"), ev(W4, "4B-07 Gaillard, S. Home Bay Positive"), ev(W4, "4B-04 Delmas, R. Transfer from another hospital Bay Pending"),
         ev(IPC, "Positif chambre individuelle et précautions contact jusqu'à la levée"), ev(IPC, "En attente, patient transféré d'un autre établissement chambre individuelle et précautions contact dès l'admission, en attente du résultat")],
        type="multi_document", difficulty="hard", style="list", domain="infection_control", rule="MRSA isolation by screen result and origin", safety=True, fmt="table: bed | patient | reason",
        modes=["french_document", "multi_document_join", "decoy_similar_rows", "table_in_protocol"], skills=["rule_application", "filtering"])
    follow_up(q16, "next_step", "What decolonisation regimen does manual IPC-MAN-01 require for an MRSA-positive patient and for how long?", "What decolonisation do the positive ones need?",
        "Nasal mupirocin three times a day and a 4% chlorhexidine wash once a day, for 5 days.",
        [kf("nasal", "mupirocin", "mupirocine"), kf("wash", "chlorhexidine", "chlorhexidine 4"), kf("duration", "5 days", "5 jours", "five days")],
        [ev(IPC, "Mupirocine nasale trois fois par jour et toilette à la chlorhexidine 4 % une fois par jour pendant 5 jours")],
        type="direct", difficulty="easy", style="explanatory", domain="infection_control", rule="MRSA decolonisation regimen", fmt="regimen | duration", modes=["french_document"], skills=["extraction"])
    follow_up(q16, "hypothetical_variation", "If the decolonisation of the patient in bed 4B-07 starts on 15/11/2026, what is the earliest date for the first clearance screen according to the manual?", "If we start decolonising bed 7 tomorrow, when's the first clearance swab?",
        "Decolonisation lasts 5 days (15 to 19/11/2026). The first clearance screen must be at least 48 hours after the end of decolonisation: not before 21/11/2026.",
        [kf("earliest date", "21/11/2026"), kf("end of decolonisation", "19/11/2026"), kf("delay", "48 hours", "48 heures")],
        [ev(IPC, "la première au moins 48 heures après la fin de la décolonisation"), ev(IPC, "pendant 5 jours")],
        type="temporal", difficulty="medium", style="conditional", domain="infection_control", rule="First clearance screen 48 hours after decolonisation ends", fmt="date", modes=["french_document", "hypothetical_variation", "derived_value"], skills=["date_arithmetic"])

    # ---------------------------------------------------------------- 17. NEWS2 (Fabre)
    OB, N2 = "OBS_Fabre_Louis_2026-11-15", "NUR-OBS-01_NEWS2_Observation_and_Escalation_Protocol_v5"
    sc = dict(S.fabre_scores())
    assert sc == {"00:00": 0, "03:00": 2, "06:00": 7, "09:00": 9, "12:00": 2}
    q17 = main_q(17,
        "From the observation chart of Louis Fabre (MRN 4459382) on 15/11/2026, calculate the NEWS2 aggregate score at each of the five observation times using protocol NUR-OBS-01, "
        "and say at what time the score first reached 5 or more.",
        "What were Mr Fabre's early warning scores on the 15th and when did it first become concerning?",
        "NEWS2: 00:00 = 0, 03:00 = 2, 06:00 = 7, 09:00 = 9, 12:00 = 2. The score first reached 5 or more at 06:00 (total 7: respiration rate 22 = 2, SpO2 95% = 1, supplemental oxygen = 2, systolic BP 108 = 1, pulse 94 = 1, alert = 0, temperature 37.8 = 0).",
        [kf("score 00:00", "0"), kf("score 03:00", "2"), kf("score 06:00", "7"), kf("score 09:00", "9"), kf("first at or above 5", "06:00")],
        [ev(OB, "06:00 22 95 oxygène 108 94 alerte 37,8"), ev(OB, "09:00 24 93 oxygène 104 104 alerte 38,4"), ev(OB, "03:00 20 94 air 118 92 alerte 37,8"), ev(N2, "Respiration rate 8 or less 9-11 12-20 21-24 25 or more"),
         ev(N2, "Pulse (per min) 40 or less 41-50 51-90 91-110 111-130 131 or more")],
        type="calculation", difficulty="hard", style="trend", domain="vital_signs", rule="NEWS2 aggregate score from raw observations", safety=True, fmt="five scores | first time at or above 5",
        modes=["french_document", "multi_document_join", "table_in_protocol", "derived_value"], skills=["score_from_table", "arithmetic"])
    follow_up(q17, "next_step", "What clinical response does protocol NUR-OBS-01 require at the time Louis Fabre's score first reached 5 or more, and with what frequency of observations?", "What did the protocol say we had to do at that point?",
        "At 06:00 the aggregate was 7, which requires an emergency response: immediate assessment by the critical care outreach team, with continuous monitoring.",
        [kf("response", "emergency response", "emergency"), kf("team", "critical care outreach"), kf("monitoring", "continuous")],
        [ev(OB, "06:00 22 95 oxygène 108 94 alerte 37,8"), ev(N2, "7 or more emergency response: immediate assessment by the critical care outreach team continuous monitoring")],
        type="multi_evidence", difficulty="medium", style="explanatory", domain="vital_signs", rule="NEWS2 clinical response", safety=True, fmt="response | frequency", modes=["table_in_protocol", "derived_value"], skills=["table_lookup"])
    follow_up(q17, "hypothetical_variation", "If Louis Fabre's SpO2 at 06:00 had been 96% instead of 95%, what would the aggregate score and the required response have been?", "What if his saturation had been 96 at six o'clock?",
        "SpO2 96% scores 0 instead of 1, so the aggregate would be 6. A score of 5 or 6 requires an urgent response: urgent review by a clinician within 30 minutes, with observations at least hourly.",
        [kf("aggregate", "6"), kf("response", "urgent response", "urgent"), kf("time frame", "30 minutes"), kf("frequency", "hourly")],
        [ev(OB, "06:00 22 95 oxygène 108 94 alerte 37,8"), ev(N2, "SpO2 (scale 1, %) 91 or less 92-93 94-95 96 or more"), ev(N2, "5 or 6 urgent response: urgent review by a clinician within 30 minutes at least hourly")],
        type="multi_evidence", difficulty="hard", style="conditional", domain="vital_signs", rule="NEWS2 sensitivity to one parameter", safety=True, fmt="score | response",
        modes=["french_document", "hypothetical_variation", "table_in_protocol", "threshold_boundary"], skills=["score_from_table", "threshold_comparison"])

    # ---------------------------------------------------------------- 18. insulin (Renard)
    IC, INS = "SCAN_20261110_1904", "PHA-INS-02_Inpatient_Insulin_Sliding_Scale_v3"
    q18 = main_q(18,
        "On 10/11/2026, compare each insulin dose given to Paul Renard (MRN 4481950) with the units required by the sliding scale in PHA-INS-02. Give the total units given, the total units required and any deviation (time, glucose, given, required).",
        "Did Mr Renard get the right insulin doses on the 10th?",
        "Given: 4 + 2 + 6 + 0 = 12 units. Required by the scale: 4 (12.4 mmol/L) + 2 (8.1) + 4 (15.6) + 0 (6.2) = 10 units. One deviation: at 17:30, glucose 15.6 mmol/L (scale 12.0-15.9 = 4 units) but 6 units were given, 2 units too many.",
        [kf("total given", "12"), kf("total required", "10"), kf("deviation time", "17:30"), kf("glucose", "15.6"), kf("excess", "2 units", "+2", "2")],
        [ev(IC, "07:30 12.4 4 AR"), ev(IC, "12:00 8.1 2 AR"), ev(IC, "17:30 15.6 6 MD"), ev(IC, "21:30 6.2 0 MD"), ev(INS, "12.0 to 15.9 4"), ev(INS, "8.0 to 11.9 2")],
        type="multi_document", difficulty="hard", style="comparison", domain="medication_safety", rule="Insulin sliding scale compliance", safety=True, fmt="totals | deviation row",
        modes=["scanned_document", "multi_document_join", "table_in_protocol", "derived_value"], skills=["table_lookup", "arithmetic", "threshold_comparison"])
    follow_up(q18, "next_step", "Is the deviation on Paul Renard's insulin chart a reportable incident under PHA-INS-02, and is there a doctor's override written on the chart?", "Is that a reportable incident?",
        "Yes: a dose that differs from the scale is a medication incident unless the doctor has written an override, and the chart states that no doctor's override is written.",
        [kf("incident", "medication incident"), kf("override", "no doctor's override", "no override", "none")],
        [ev(INS, "A dose that differs from the scale is a medication incident unless the doctor has written an override."), ev(IC, "No doctor's override is written on the chart.")],
        type="multi_document", difficulty="medium", style="yes_no", domain="medication_safety", rule="Insulin deviation without override", safety=True, fmt="yes/no with reason", modes=["scanned_document", "multi_document_join"], skills=["rule_application"])
    follow_up(q18, "hypothetical_variation", "What dose would the sliding scale require if Paul Renard's 12:00 glucose had been exactly 12.0 mmol/L?", "And at lunchtime if it had been exactly 12.0?",
        "12.0 mmol/L falls in the 12.0 to 15.9 band: 4 units of insulin aspart.",
        [kf("dose", "4 units", "4")], [ev(INS, "12.0 to 15.9 4")],
        type="direct", difficulty="easy", style="conditional", domain="medication_safety", rule="Insulin scale boundary", safety=True, fmt="units", modes=["hypothetical_variation", "threshold_boundary", "table_in_protocol"], skills=["table_lookup"])

    # ---------------------------------------------------------------- 19. formulary (Caron)
    CC, FOR, DT = "MAR_Caron_Sylvie_2026-11-18", "PHA-FOR-00_Hospital_Formulary_2026-2027", "2026-11-16_DT_approval_tolvaptan_MRN-4486603"
    assert [n for n, _, _ in S.caron_flagged()] == ["Tolvaptan", "Sacubitril/valsartan", "Linaclotide"]
    q19 = main_q(19,
        "On 18/11/2026, which medicines on Sylvie Caron's (MRN 4486603) prescription chart are restricted or non-formulary in the 2026-2027 formulary, and for which of them is there a documented approval?",
        "Is Mrs Caron on any non-formulary or restricted drugs, and are they approved?",
        "Three: tolvaptan (non-formulary), sacubitril/valsartan (restricted, cardiology consultant initiation) and linaclotide (restricted, gastroenterology consultant initiation). "
        "Only tolvaptan has a documented approval (Drug and Therapeutics Committee e-mail of 16/11/2026); the e-mail states that none was requested for any other non-formulary or restricted medicine, and no specialty initiation is documented for the two restricted drugs.",
        [kf("non-formulary", "tolvaptan"), kf("restricted 1", "sacubitril"), kf("restricted 2", "linaclotide"), kf("approved", "tolvaptan"), kf("approval date", "16/11/2026")],
        [ev(CC, "Tolvaptan 15 mg once daily Dr Vasseur"), ev(CC, "Sacubitril/valsartan 49/51 mg twice daily Dr Vasseur"), ev(CC, "Linaclotide 290 micrograms once daily Dr Vasseur"),
         ev(FOR, "Tolvaptan NF individual patient approval by the Drug and Therapeutics Committee (D&T)"), ev(FOR, "Sacubitril/valsartan R cardiology consultant initiation"),
         ev(FOR, "Linaclotide R gastroenterology consultant initiation"), ev(DT, "No approval has been requested for any other non-formulary or restricted medicine for this patient.")],
        type="multi_document", difficulty="hard", style="list", domain="medication_safety", rule="Formulary status and approval", safety=False, fmt="table: medicine | status | approval documented?",
        modes=["multi_document_join", "email_source", "table_in_protocol", "absence_of_document"], skills=["filtering", "absence_reasoning"])
    follow_up(q19, "drill_down", "Until what date is the tolvaptan approval for Sylvie Caron valid, and who granted it?", "Until when is the tolvaptan approved, and by whom?",
        "The approval runs for 14 days, from 16/11/2026 to 29/11/2026 inclusive, and was granted by Dr Élise Maurel, Chair of the Drug and Therapeutics Committee.",
        [kf("valid until", "29/11/2026"), kf("approver", "Maurel")],
        [ev(DT, "for 14 days, from 16/11/2026 to 29/11/2026 inclusive"), ev(DT, "Dr Élise Maurel, Chair of the Drug and Therapeutics Committee")],
        type="direct", difficulty="easy", style="lookup", domain="medication_safety", rule="Approval validity", fmt="date and name", modes=["email_source"], skills=["extraction"])
    follow_up(q19, "drill_down", "Which specialty must initiate sacubitril/valsartan according to the formulary?", "Who is allowed to start the sacubitril/valsartan?",
        "A cardiology consultant: sacubitril/valsartan is restricted (R) with cardiology consultant initiation.",
        [kf("specialty", "cardiology")], [ev(FOR, "Sacubitril/valsartan R cardiology consultant initiation")],
        type="direct", difficulty="easy", style="lookup", domain="medication_safety", rule="Restricted drug initiation", fmt="one specialty", modes=["table_in_protocol"], skills=["extraction"])

    # ---------------------------------------------------------------- 20. unanswerable + false premise (Ferrand)
    q20 = main_q(20, "What was Odile Ferrand's (MRN 4480110) HbA1c result during her admission?", "What was Mrs Ferrand's HbA1c?",
        "This cannot be established from the documents: no HbA1c was reported. Her laboratory reports of 16/11/2026 and 17/11/2026 do not include this analyte and no other document gives it.",
        [], [], type="negative", difficulty="medium", style="lookup", domain="laboratory", rule="Analyte not reported in the corpus", fmt="abstention", modes=["absence_of_document", "french_document"],
        answerable=False, skills=["abstention"])
    follow_up(q20, "false_premise", "Why was Odile Ferrand started on insulin?", "Why did they put her on insulin?",
        "She was not started on insulin: her prescription chart of 16/11/2026 states that no insulin or antidiabetic medicine is prescribed. The question rests on a false premise.",
        [kf("correction", "no insulin", "not started", "not prescribed", "Aucune insuline", "aucune insuline")],
        [ev(FPR, "Aucune insuline ni antidiabétique n'est prescrit.")],
        type="direct", difficulty="medium", style="explanatory", domain="medication_safety", rule="False premise: insulin never prescribed", fmt="correction of the premise",
        modes=["false_premise", "french_document"], skills=["premise_checking"], depends=False)
    follow_up(q20, "scope_change", "What were Odile Ferrand's potassium results on 16/11/2026 and 17/11/2026, and were they within range?", "OK, and her potassium?",
        "Potassium was 4.6 mmol/L on both 16/11/2026 and 17/11/2026, within the reference interval of 3.5 to 5.0 mmol/L.",
        [kf("potassium", "4.6", "4,6"), kf("range", "within", "normal", "dans les valeurs")],
        [ev(F16, "Potassium 4,6 mmol/L 3,5 - 5,0"), ev(F17, "Potassium 4,6 mmol/L 3,5 - 5,0")],
        type="multi_document", difficulty="easy", style="lookup", domain="laboratory", rule="Recover from an abstention with an answerable question", fmt="two values",
        modes=["french_document", "same_analyte_multiple_dates"], skills=["extraction"], depends=False)

    # ---------------------------------------------------------------- 21. isolation probe
    main_q(21, "What was Zoé Lambert's INR on 02/11/2026?", "What was Zoé Lambert's INR on 2 November?",
        "This cannot be established from the documents available in this store: no document of this store concerns a patient named Zoé Lambert.",
        [], [], type="negative", difficulty="medium", style="lookup", domain="privacy", rule="Store isolation probe", fmt="abstention", modes=["absence_of_document"], answerable=False, skills=["abstention"])
    for r in ROWS:
        if r["metadata"]["follow_up_of"] is None:
            r["metadata"]["follow_up_ids"] = CONV[r["id"]][1:]


def write():
    out = ROOT / "datasets"
    out.mkdir(exist_ok=True)
    (out / "carebench_v1.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS), "utf-8")
    simple = []
    for r in ROWS:
        m = r["metadata"]
        docs = list(dict.fromkeys(f"{e['document_id']}.{MAN[e['document_id']]['filename'].rsplit('.', 1)[1]}" for e in r["evidence"]))
        simple.append(dict(id=r["id"], conversation_id=m["conversation_id"], turn=m["turn"], follow_up_type=m["follow_up_type"] or "", question=r["question"],
                           question_natural=r["question_natural"], answer=r["reference_answer"], documents=docs,
                           pages=[f"{e['document_id']}:{e['page']}" for e in r["evidence"]], answerable=m["answerable"]))
    (out / "carebench_v1_simple.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in simple), "utf-8")
    with open(out / "carebench_v1_simple.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(simple[0]))
        w.writeheader()
        for r in simple:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in r.items()})
    by_id = {r["id"]: r for r in ROWS}
    conv = [dict(conversation_id=cid, n_turns=len(ids), turns=[dict(id=i, turn=by_id[i]["metadata"]["turn"], question=by_id[i]["question"], question_natural=by_id[i]["question_natural"],
                                                                    reference_answer=by_id[i]["reference_answer"], follow_up_type=by_id[i]["metadata"]["follow_up_type"]) for i in ids])
            for cid, ids in CONV.items()]
    (out / "carebench_v1_conversations.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in conv), "utf-8")
    print(f"{len(ROWS)} rows: {len(CONV)} main questions + {len(ROWS) - len(CONV)} follow-ups -> {out}")


if __name__ == "__main__":
    build()
    write()
