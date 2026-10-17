#!/usr/bin/env python3
"""Generate the CareBench corpus (PDF + .eml) from scenario.py.

    python carebench/tools/corpus.py        # -> corpus/documents/*, corpus/manifest.json, corpus/ocr_reference/*, isolation_probe/

Deterministic: same code, same files. Scanned documents are rasterised (no text layer); their reference text, used
only to check evidence quotes, goes to corpus/ocr_reference/ and must never be ingested.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageFilter  # noqa: E402

import pdfkit as K  # noqa: E402
from pdfkit import table, kv  # noqa: E402
import scenario as S  # noqa: E402
from scenario import D, P, fd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
DOCS = CORPUS / "documents"
OCR = CORPUS / "ocr_reference"
PROBE = ROOT / "isolation_probe"
MANIFEST: list[dict] = []
SCAN_SEQ: dict = {}

H1 = lambda t: ("h1", t)
H2 = lambda t: ("h2", t)
H3 = lambda t: ("h3", t)
PP = lambda t: ("p", t)
LI = lambda t: ("li", t)
SM = lambda t: ("small", t)
TB = lambda *a, **k: ("table", table(*a, **k))
KV = lambda pairs, **k: ("table", kv(pairs, **k))
PB = ("pb",)
SP = lambda n=3: ("sp", n)


# ------------------------------------------------------------------ emit
def scan(native: Path, out: Path, seed: int) -> None:
    rnd = random.Random(seed)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "150", "-gray", "-png", str(native), f"{td}/p"], check=True)
        pages = []
        for png in sorted(Path(td).glob("p*.png")):
            im = Image.open(png).convert("L").rotate(rnd.uniform(-1.2, 1.2), resample=Image.BICUBIC, fillcolor=255)
            im = Image.blend(im, Image.effect_noise(im.size, 18).convert("L"), 0.06).filter(ImageFilter.GaussianBlur(0.45))
            im = im.point(lambda v: max(0, min(255, int((v - 18) * 1.08))))
            im.paste(Image.new("L", (14, im.size[1]), 120), (0, 0))
            pages.append(im.convert("RGB"))
        pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:], quality=72)


def slug(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().replace(" ", "-")


def pdf_text(p: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, check=True).stdout


def n_pages(p: Path) -> int:
    out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, check=True).stdout
    return int(next(l for l in out.splitlines() if l.startswith("Pages:")).split()[1])


def emit(filename: str, dtype: str, title: str, lang: str, blocks, date: dt.date, patient: str = "", banner=None,
         land=False, scanned=False, role="filler", out_dir: Path | None = None):
    out_dir = out_dir or DOCS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    ref = filename.rsplit(".", 1)[0]
    if scanned:
        with tempfile.TemporaryDirectory() as td:
            native = Path(td) / "n.pdf"
            K.build(native, ref, blocks, banner=banner, land=land, title=title)
            OCR.mkdir(parents=True, exist_ok=True)
            (OCR / f"{ref}.txt").write_text(pdf_text(native), "utf-8")
            scan(native, path, seed=len(MANIFEST) + 7)
    else:
        K.build(path, ref, blocks, banner=banner, land=land, title=title)
    if out_dir == DOCS:
        data = path.read_bytes()
        MANIFEST.append(dict(document_id=ref, filename=filename, document_type=dtype, title=title, language=lang,
                             date=date.isoformat(), patient_mrn=P[patient].mrn if patient else "", pages=n_pages(path),
                             scanned=scanned, role=role, sha256=hashlib.sha256(data).hexdigest()))


def write_eml(filename, frm, to, when: dt.datetime, subject, body, lang="en", role="filler", sender=""):
    import email.policy
    import html
    from email.message import EmailMessage
    from email.utils import format_datetime, formataddr
    m = EmailMessage()
    m["Message-ID"] = f"<{hashlib.sha1((frm + subject + when.isoformat()).encode()).hexdigest()[:24]}@ch-saint-aubin.example>"
    m["Date"] = format_datetime(when.replace(tzinfo=dt.timezone(dt.timedelta(hours=1))))
    m["From"] = formataddr((sender, frm)) if sender else frm
    m["To"] = to
    m["Subject"] = subject
    m["Content-Language"] = "fr-FR" if lang == "fr" else "en-GB"
    m.set_content(body, charset="utf-8")
    paras = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in body.split("\n\n"))
    m.add_alternative(f"<html><body style=\"font-family:Calibri,Arial,sans-serif\">{paras}</body></html>", subtype="html", charset="utf-8")
    path = DOCS / filename
    path.write_bytes(m.as_bytes(policy=email.policy.SMTP))
    MANIFEST.append(dict(document_id=filename.rsplit(".", 1)[0], filename=filename, document_type="email", title=subject,
                         language=lang, date=when.date().isoformat(), patient_mrn="", pages=1, scanned=False, role=role,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))


# ------------------------------------------------------------------ shared building blocks
def demog(p, extra=(), on=None):
    f = p.lang == "fr"
    age = p.age_on(on or D(2026, 11, 16))
    return KV([("Patient", f"{p.last.upper()} {p.first}"),
               ("Date of birth / sex" if not f else "Date de naissance / sexe", f"{fd(p.dob)} / {p.sex}"),
               ("Age" if not f else "Âge", f"{age} years" if not f else f"{age} ans"),
               ("MRN", p.mrn), *extra])


def lab_blocks(p, d: dt.date, panel: dict, requester: str, ward: str, collected: str, extra_rows=(), final_note="",
               keys=None):
    f = p.lang == "fr"
    L = lambda en, fr: fr if f else en
    keys = keys or [a[0] for a in S.ANALYTES]
    chem = [k for k in keys if k in panel and k not in S.HAEM]
    haem = [k for k in keys if k in panel and k in S.HAEM]

    def rows(ks):
        out = []
        for k in ks:
            a = S.AN[k]
            out.append((a[2] if f else a[1], S.fmt_val(k, panel[k], p.lang), a[3], S.fmt_range(k, p, p.lang), S.flag(p, k, panel[k])))
        return out
    hdr = [L("Analyte", "Analyse"), L("Result", "Résultat"), "Unit" if not f else "Unité", L("Reference interval", "Valeurs de référence"), "Flag"]
    w = [62, 24, 24, 40, 14]
    b = [H1(L("Laboratory report - clinical chemistry and haematology", "Compte rendu de biologie médicale")),
         demog(p, [(L("Requesting clinician", "Prescripteur"), requester), (L("Ward", "Service"), ward),
                   (L("Sample collected", "Prélèvement"), collected), (L("Report date", "Date du compte rendu"), fd(d))], on=d),
         H2(L("Clinical chemistry", "Biochimie")), TB(hdr, rows(chem) + list(extra_rows), w, align="lrlll")]
    if haem:
        b += [PB, H2(L("Haematology", "Hématologie")), TB(hdr, rows(haem), w, align="lrlll")]
    b += [SM(L("H = above the reference interval, L = below. Reference intervals depend on sex and are those of the "
               "Saint-Aubin laboratory. Results are valid only for the sample identified above.",
               "H = au-dessus de l'intervalle de référence, L = en dessous. Les intervalles dépendent du sexe et sont ceux du "
               "laboratoire de Saint-Aubin. Les résultats ne valent que pour l'échantillon identifié ci-dessus."))]
    if final_note:
        b.append(PP(final_note))
    b += [PB, H2(L("Laboratory information", "Informations du laboratoire")),
          PP(L("The medical biology laboratory of the Centre Hospitalier Saint-Aubin operates under its quality management system "
               "and takes part in external quality assessment programmes for every analyte reported above. Methods are "
               "photometric and immunoassay on the central analyser; haematology is performed by flow cytometry. Samples are "
               "kept for seven days after the report date and can be re-assayed on request.",
               "Le laboratoire de biologie médicale du Centre Hospitalier Saint-Aubin travaille selon son système de management de "
               "la qualité et participe aux programmes d'évaluation externe pour chaque analyse rendue ci-dessus. Les méthodes sont "
               "photométriques et immunologiques sur l'automate central ; l'hématologie est réalisée par cytométrie en flux. Les "
               "échantillons sont conservés sept jours et peuvent être redosés sur demande.")),
          PP(L("Critical values are telephoned to the requesting ward and recorded in the laboratory information system. A "
               "result outside its reference interval is not necessarily clinically significant: interpretation belongs to the "
               "requesting clinician in the light of the patient's condition.",
               "Les valeurs critiques sont téléphonées au service demandeur et tracées dans le système d'information du laboratoire. "
               "Un résultat hors intervalle n'est pas nécessairement significatif : l'interprétation revient au clinicien "
               "prescripteur au vu de l'état du patient.")),
          PP(L("Queries: biochemistry secretariat, extension 4412, weekdays 08:00-17:00.", "Questions : secrétariat de biochimie, poste 4412, jours ouvrés 08h00-17h00."))]
    return b


def lab_pdf(p, d, panel, requester, ward, collected, **kw):
    fn = f"LAB_{slug(p.last)}_{slug(p.first)}_{d.isoformat()}.pdf"
    emit(fn, "lab_report", f"Laboratory report {p.name} {fd(d)}", p.lang, lab_blocks(p, d, panel, requester, ward, collected, **kw),
         d, p.key, banner=p.banner(), role=kw.pop("role", "evidence") if False else "evidence")
    return fn


# governance filler (never contains clinical thresholds that could be confused with the content tables)
GOV_EN = [
    "This document is controlled. Printed copies are uncontrolled: the current version is held on the hospital document "
    "management system and a printed copy must be checked against it before use.",
    "The document owner reviews the content at least every three years or earlier when national guidance, a serious incident or an "
    "audit finding requires it. Interim changes are approved by the relevant committee chair and recorded in the revision history.",
    "Compliance is audited by the clinical audit department on a rolling sample of records. Results are reported to the quality and "
    "patient safety committee, which agrees actions with the ward managers and monitors their completion.",
    "Staff who identify a deviation from this document, or a situation it does not cover, should discuss it with the senior clinician "
    "on duty and report it through the incident reporting system. Reporting is a learning tool and not a disciplinary process.",
    "Training on this document is part of the induction programme for clinical staff and is refreshed through the annual mandatory "
    "training cycle. Agency and locum staff receive a short briefing at the start of their first shift.",
    "Equality and diversity: this document has been assessed for its effect on patients and staff with protected characteristics. "
    "Reasonable adjustments, interpreters and accessible formats are available through the patient experience team.",
    "Data protection: any patient information handled under this document is processed in accordance with the data protection "
    "policy of the hospital. Access to records is limited to staff involved in the care of the patient.",
    "Where this document refers to a role (for example the ward pharmacist or the senior nurse), the post-holder on duty carries out "
    "the task or delegates it to a suitably trained colleague who remains accountable to them.",
]
GOV_FR = [
    "Ce document est maîtrisé. Les copies imprimées ne sont pas maîtrisées : la version en vigueur est conservée dans la gestion "
    "documentaire de l'établissement et toute copie papier doit être vérifiée avant usage.",
    "Le pilote du document le révise au moins tous les trois ans, ou plus tôt si une recommandation nationale, un événement indésirable "
    "grave ou un audit l'exigent. Les modifications intermédiaires sont validées par le président de l'instance concernée.",
    "La conformité est évaluée par le service d'audit clinique sur un échantillon glissant de dossiers. Les résultats sont présentés à "
    "la commission qualité et sécurité des soins qui convient des actions avec les cadres de santé.",
    "Tout professionnel qui constate un écart par rapport à ce document, ou une situation non couverte, en parle au senior de garde "
    "et le signale dans le système de déclaration des événements indésirables, dans une démarche d'apprentissage.",
]


def revision_table(code, owner, d):
    rows = [("1.0", fd(d.replace(year=d.year - 5)), owner, "First issue"),
            ("2.0", fd(d.replace(year=d.year - 3)), owner, "Triennial review; format harmonised"),
            ("3.0", fd(d.replace(year=d.year - 1, month=6)), owner, "Tables updated after clinical audit"),
            ("current", fd(d), owner, "Review and re-issue")]
    return TB(["Version", "Date", "Author", "Summary of change"], rows, [22, 28, 50, 80])


def protocol(filename, code, title, version, owner, d: dt.date, sections, lang="en", extra_pages=0, land=False,
             approved="Quality and Patient Safety Committee", role="evidence"):
    f = lang == "fr"
    rng = random.Random(code)
    gov = GOV_FR if f else GOV_EN
    b = [H1(title),
         KV([("Reference", f"{code} v{version}"), ("Owner", owner), ("Approved by", approved), ("Effective date", fd(d)),
             ("Next review", fd(d.replace(year=d.year + 3))), ("Applies to", "All clinical areas of the Centre Hospitalier Saint-Aubin")], widths=(42, 128 if not land else 215))]
    for i, (head, blocks) in enumerate(sections, 1):
        b += [H2(f"{i}. {head}"), *blocks]
    n = len(sections)
    b += [H2(f"{n + 1}. Governance, audit and training"), *[PP(s) for s in gov[:4]]]
    b += [H2(f"{n + 2}. Revision history"), revision_table(code, owner, d)]
    for k in range(extra_pages):
        b += [PB, H2(f"Annex {chr(65 + k)}. Implementation notes"), *[PP(s) for s in rng.sample(gov, len(gov))],
              *[PP(s) for s in rng.sample(gov, 4)]]
    emit(filename, "protocol", f"{title} ({code})", lang, b, d, land=land, role=role)


# ------------------------------------------------------------------ hospital documents (protocols, policies)
def hospital_documents():
    d0 = D(2026, 1, 12)
    # --- renal dosing
    egfr_rows = [("Serum creatinine in µmol/L", "divide by 88.4 to obtain mg/dL (Scr)"), ("Female", "kappa = 0.7, alpha = -0.241, multiply the result by 1.012"),
                 ("Male", "kappa = 0.9, alpha = -0.302"), ("Age", "whole years on the day of the sample")]
    protocol("PHA-REN-02_Renal_Dose_Adjustment_Protocol_v4.pdf", "PHA-REN-02", "Renal Dose Adjustment Protocol", "4",
             "Chief Pharmacist", D(2026, 3, 2), [
        ("Purpose and scope", [PP("This protocol sets out how renal function is estimated and how the doses of renally cleared medicines are adjusted "
                                  "for adult inpatients. It applies to prescribers, ward pharmacists and nurses. Children, dialysis patients and "
                                  "patients with acute kidney injury follow separate guidance.")]),
        ("Estimating renal function", [
            PP("Renal function is expressed as the estimated glomerular filtration rate (eGFR) calculated with the CKD-EPI 2021 equation: "
               "<b>eGFR = 142 x min(Scr/kappa, 1)^alpha x max(Scr/kappa, 1)^-1.200 x 0.9938^Age x 1.012 [if female]</b>, "
               "in mL/min/1.73 m2."),
            TB(["Term", "Rule"], egfr_rows, [50, 120]),
            PP("The eGFR is rounded to the nearest whole number before the dose band is read. The laboratory reports creatinine only; "
               "the eGFR is calculated by the prescriber or the ward pharmacist and written in the notes.")]),
        ("Enoxaparin, treatment dose", [
            TB(["eGFR band (mL/min/1.73 m2)", "Treatment dose", "Monitoring"],
               [("30 or above", "1 mg/kg every 12 hours", "none routinely"), ("15 to 29", "1 mg/kg once daily", "anti-Xa level after the third dose"),
                ("below 15", "do not use; discuss with the pharmacist", "-")], [50, 70, 50]),
            PP("Use the actual body weight in kilograms at admission. The calculated dose is rounded to the nearest prefilled syringe "
               "(20, 40, 60, 80, 100, 120 or 150 mg).")]),
        ("Other renally cleared medicines", [
            TB(["Medicine", "eGFR band", "Adjustment"],
               [("Metformin", "45 or above", "no change"), ("Metformin", "30 to 44", "maximum 1,000 mg per day"), ("Metformin", "below 30", "stop"),
                ("Gentamicin", "below 50", "extended interval, level-guided"), ("Apixaban (atrial fibrillation)", "15 to 29", "use with caution; 2.5 mg twice daily if two of age 80 or more, weight 60 kg or less, creatinine 133 micromol/L or more"),
                ("Ramipril", "below 30", "start at 1.25 mg and titrate")], [50, 30, 90])]),
        ("Responsibilities", [PP("The prescriber records the eGFR, the band and the resulting dose in the notes. The ward pharmacist verifies the "
                                 "calculation at the next review and escalates unresolved discrepancies to the consultant.")]),
    ], extra_pages=2)
    # --- antibiotic policy
    protocol("PHA-ANT-01_Antibiotic_Prescribing_Policy_v7.pdf", "PHA-ANT-01", "Antibiotic Prescribing Policy", "7",
             "Antimicrobial Stewardship Group", D(2026, 2, 16), [
        ("Principles", [PP("Prescribe according to the indication tables below, document the indication and the planned duration on the drug chart, and "
                           "review every antibiotic at 48 to 72 hours (start smart, then focus). Intravenous treatment is reviewed daily for a switch to oral.")]),
        ("Penicillin allergy", [
            PP("Record the nature of the reaction. A <b>severe or immediate reaction</b> (anaphylaxis, angioedema, urticaria with hypotension or bronchospasm) "
               "is a contraindication to every penicillin, including amoxicillin, co-amoxiclav and piperacillin-tazobactam. A non-severe, delayed rash "
               "allows a cephalosporin after discussion with the pharmacist."),
            PP("The allergy status must be copied from the admission note to the drug chart on admission. A discrepancy between the two is a reportable medication incident.")]),
        ("Community-acquired pneumonia (CAP)", [
            TB(["Situation", "First-line regimen", "Route"],
               [("Moderate CAP, no allergy", "Amoxicillin 1 g three times daily", "oral"), ("Moderate CAP, severe penicillin allergy", "Doxycycline 200 mg on day 1, then 100 mg once daily", "oral"),
                ("Severe CAP", "Ceftriaxone 2 g once daily (plus clarithromycin 500 mg twice daily)", "intravenous")], [50, 90, 30]),
            PP("Total duration of treatment is 5 days. <b>Intravenous therapy is limited to 3 days</b>; from day 4 the patient must be switched to the oral regimen "
               "unless the infectious diseases team documents a reason to continue.")]),
        ("Urinary tract infection", [TB(["Situation", "First-line regimen", "Duration"],
                                        [("Lower, female", "Nitrofurantoin 100 mg modified-release twice daily", "3 days"), ("Lower, male", "Trimethoprim 200 mg twice daily", "7 days"),
                                         ("Pyelonephritis", "Co-amoxiclav 1.2 g three times daily IV, then oral", "7 days")], [50, 90, 30])]),
        ("Surgical antibiotic prophylaxis", [
            TB(["Item", "Requirement"],
               [("Agent (clean-contaminated abdominal surgery)", "Cefazolin intravenous"), ("Dose", "2 g; 3 g if body weight is 120 kg or more"),
                ("Timing", "within 60 minutes before skin incision"), ("Re-dosing", "repeat the dose if the operation lasts more than 4 hours or blood loss exceeds 1,500 mL"),
                ("Duration", "single dose; no post-operative continuation for clean-contaminated cases")], [70, 100]),
            PP("The time of administration and the time of incision are both recorded on the anaesthetic record. Each month the audit team checks compliance with "
               "dose and timing and reports it to the surgical directorate.")]),
        ("Skin and soft-tissue infection", [TB(["Situation", "First-line regimen", "Duration"],
                                               [("Cellulitis", "Flucloxacillin 1 g four times daily", "5 days"), ("Cellulitis, severe penicillin allergy", "Clarithromycin 500 mg twice daily", "5 days")], [50, 90, 30])]),
    ], extra_pages=5)
    # --- warfarin
    protocol("PHA-ANC-03_Warfarin_Dosing_Nomogram_v3.pdf", "PHA-ANC-03", "Warfarin Dosing Nomogram (Maintenance Phase)", "3",
             "Anticoagulation Pharmacist", D(2026, 4, 6), [
        ("Scope", [PP("For outpatients and inpatients with a target INR of 2.0 to 3.0 who are on stable maintenance warfarin. Initiation, mechanical valves and "
                      "a target INR above 3.0 follow separate guidance.")]),
        ("Maintenance nomogram", [
            TB(["INR", "Action", "Next INR"],
               [("below 1.5", "increase weekly dose by 15%", "in 4 days"), ("1.5 to 1.9", "increase weekly dose by 10%", "in 7 days"),
                ("2.0 to 3.0", "no change", "in 4 weeks if stable, otherwise 2 weeks"), ("3.1 to 3.9", "decrease weekly dose by 10%", "in 7 days"),
                ("4.0 to 4.9", "omit one dose, then decrease weekly dose by 15%", "in 3 days"),
                ("5.0 or above", "omit two doses, contact the anticoagulation pharmacist, then decrease weekly dose by 20%", "in 1 day")], [30, 100, 40]),
            PP("The next INR date is counted from the date of the sample being acted upon. The new weekly dose is calculated to one decimal place; the pharmacist then agrees a practicable tablet schedule with the patient.")]),
        ("Documentation", [PP("Each INR, the dose decision and the next test date are recorded in the anticoagulation record. The patient receives a written dosing calendar.")]),
    ], extra_pages=2)
    # --- NEWS2
    protocol("NUR-OBS-01_NEWS2_Observation_and_Escalation_Protocol_v5.pdf", "NUR-OBS-01", "NEWS2 Observation and Escalation Protocol", "5",
             "Chief Nursing Officer", D(2026, 5, 4), [
        ("Scoring", [
            PP("The National Early Warning Score 2 (NEWS2) is the sum of seven parameters, each scored 0 to 3, plus 2 points if the patient is receiving supplemental oxygen."),
            TB(["Score", "3", "2", "1", "0", "1", "2", "3"],
               [("Respiration rate", "8 or less", "", "9-11", "12-20", "", "21-24", "25 or more"),
                ("SpO2 (scale 1, %)", "91 or less", "92-93", "94-95", "96 or more", "", "", ""),
                ("Air or oxygen", "", "oxygen", "", "air", "", "", ""),
                ("Systolic BP (mmHg)", "90 or less", "91-100", "101-110", "111-219", "", "", "220 or more"),
                ("Pulse (per min)", "40 or less", "", "41-50", "51-90", "91-110", "111-130", "131 or more"),
                ("Consciousness", "", "", "", "Alert", "", "", "Confusion, V, P or U"),
                ("Temperature (C)", "35.0 or less", "", "35.1-36.0", "36.1-38.0", "38.1-39.0", "39.1 or more", "")],
               [38, 22, 18, 20, 22, 20, 22, 28], size=7.6)]),
        ("Clinical response", [
            TB(["Aggregate NEWS2", "Response", "Minimum frequency of observations"],
               [("0", "routine monitoring", "every 12 hours"), ("1 to 4", "ward-based response: registered nurse decides", "every 4 to 6 hours"),
                ("3 in a single parameter", "urgent ward-based response", "as directed"),
                ("5 or 6", "urgent response: urgent review by a clinician within 30 minutes", "at least hourly"),
                ("7 or more", "emergency response: immediate assessment by the critical care outreach team", "continuous monitoring")], [40, 85, 45])]),
        ("Recording", [PP("The aggregate score is calculated at every set of observations from the chart values using the table above. The time of the escalation call and the name "
                          "of the clinician who answered are recorded in the notes.")]),
    ], extra_pages=2)
    # --- interaction bulletin (landscape)
    ints = sorted(S.INTERACTIONS, key=lambda r: (r[0], r[1]))
    protocol("PHA-INT-05_Drug_Interaction_Bulletin_Q4-2026.pdf", "PHA-INT-05", "Drug Interaction Bulletin, Fourth Quarter 2026", "11",
             "Medicines Information Pharmacist", D(2026, 10, 5), [
        ("How to use this bulletin", [PP("The pairs below are those most often encountered on the wards. Severity: <b>Major</b> - avoid or manage actively, document the decision; "
                                         "<b>Moderate</b> - monitor; <b>Minor</b> - no action. A pair that is not listed has not been assessed, which does not mean it is safe.")]),
        ("Interaction pairs", [TB(["Medicine A", "Medicine B", "Severity", "Effect", "Management"], [list(r) for r in ints],
                                  [34, 40, 20, 70, 103], size=7.8)]),
    ], extra_pages=1, land=True)
    # --- Calendrier vaccinal (FR)
    protocol("IMM-SCH-01_Calendrier_vaccinal_adulte_v2.pdf", "IMM-SCH-01", "Calendrier vaccinal de l'adulte (usage hospitalier)", "2",
             "Équipe opérationnelle d'hygiène", D(2026, 9, 21), [
        ("Objet", [PP("Ce document résume les vaccinations à vérifier lors de toute consultation ou hospitalisation d'un adulte. Il complète, sans la remplacer, la "
                      "recommandation nationale. Le statut vaccinal est évalué à la date de la consultation.")]),
        ("Vaccins et règles", [
            TB(["Vaccin", "Population", "Règle"],
               [("dTcaP (tétanos, diphtérie, coqueluche)", "tous les adultes", "rappel tous les 10 ans (à 10 ans révolus après la dernière dose)"),
                ("Grippe saisonnière", "tous les adultes de 65 ans et plus", "une dose chaque saison, à partir du 15 octobre"),
                ("Pneumocoque (PCV20)", "65 ans et plus", "une dose unique, sans rappel"),
                ("Zona (vaccin recombinant, RZV)", "65 ans et plus", "2 doses espacées de 2 à 6 mois ; si l'intervalle de 6 mois est dépassé, administrer la seconde dose dès que possible sans reprendre le schéma"),
                ("COVID-19", "65 ans et plus", "une dose chaque automne, à partir du 1er octobre")], [52, 42, 76])]),
        ("Interprétation", [PP("Un vaccin est « en retard » lorsque la date d'échéance est dépassée, « à faire » lorsqu'il est indiqué et jamais administré ou que la saison en cours n'est pas couverte, "
                               "et « à jour » dans les autres cas. Les fenêtres d'intervalle se comptent en mois calendaires à partir de la date de la première dose.")]),
    ], lang="fr", extra_pages=2)
    # --- nodule guideline
    protocol("RAD-FUP-02_Pulmonary_Nodule_Follow-up_Guideline_v2.pdf", "RAD-FUP-02", "Follow-up of Incidental and Known Pulmonary Nodules", "2",
             "Thoracic Imaging Lead", D(2026, 6, 15), [
        ("Measurement", [PP("Nodules are measured as the longest axial diameter in millimetres on lung windows. Change is expressed as the percentage change in longest diameter between the "
                            "two most recent examinations.")]),
        ("Action by size and change", [
            TB(["Finding", "Action"],
               [("Solid nodule under 6 mm, no risk factor", "no follow-up"),
                ("Known nodule, increase in longest diameter under 20%", "repeat CT 12 months after the latest examination"),
                ("Known nodule, increase in longest diameter of 20% or more", "refer to the thoracic multidisciplinary team (MDT) within 14 days of the report date; PET-CT before the MDT"),
                ("New solid nodule of 8 mm or more", "refer to the thoracic MDT within 14 days of the report date")], [80, 90])]),
    ], extra_pages=1)
    # --- paediatric handbook
    protocol("PAE-DOS-01_Paediatric_Dosing_Handbook_2026.pdf", "PAE-DOS-01", "Paediatric Dosing Handbook", "2026",
             "Paediatric Pharmacist", D(2026, 1, 26), [
        ("Principles", [PP("Doses are calculated on the current body weight in kilograms. Use the weight measured at admission; never an estimate when a measured weight exists. Express doses "
                           "in milligrams and volumes in millilitres. Volumes are rounded down to the nearest 0.5 mL.")]),
        ("Paracetamol", [
            TB(["Item", "Rule"],
               [("Single dose", "15 mg/kg per dose"), ("Interval", "every 6 hours (minimum 4 hours)"), ("Maximum doses", "4 doses in 24 hours"),
                ("Maximum daily dose", "60 mg/kg per 24 hours, not exceeding 4 g"), ("Maximum single dose", "1 g"),
                ("Oral suspension", "120 mg in 5 mL (24 mg/mL)")], [50, 120]),
            PP("A prescription above the single-dose or daily limit must not be dispensed; the pharmacist contacts the prescriber.")]),
        ("Ibuprofen", [TB(["Item", "Rule"], [("Single dose", "5 to 10 mg/kg per dose"), ("Interval", "every 6 to 8 hours"), ("Maximum daily dose", "30 mg/kg per 24 hours")], [50, 120])]),
        ("Amoxicillin", [TB(["Item", "Rule"], [("Standard dose", "25 mg/kg three times daily"), ("Maximum", "1 g per dose")], [50, 120])]),
    ], extra_pages=3)
    # --- IPC manual (FR)
    protocol("IPC-MAN-01_Manuel_de_prevention_des_infections_v6.pdf", "IPC-MAN-01", "Manuel de prévention des infections associées aux soins", "6",
             "Équipe opérationnelle d'hygiène", D(2026, 4, 20), [
        ("Précautions standard", [PP("L'hygiène des mains, le port de gants pour tout risque d'exposition à des liquides biologiques, la gestion des excreta et le bionettoyage s'appliquent à tous les patients, "
                                     "quel que soit leur statut infectieux.")]),
        ("SARM (Staphylococcus aureus résistant à la méticilline)", [
            PP("<b>Dépistage.</b> Les patients transférés d'un autre établissement ou venant d'un établissement d'hébergement sont dépistés à l'admission (nez et périnée)."),
            TB(["Statut du dépistage", "Mesure"],
               [("Positif", "chambre individuelle et précautions contact jusqu'à la levée"),
                ("En attente, patient transféré d'un autre établissement", "chambre individuelle et précautions contact dès l'admission, en attente du résultat"),
                ("En attente, autre provenance", "précautions standard"), ("Négatif", "précautions standard")], [70, 100]),
            PP("<b>Décolonisation.</b> Mupirocine nasale trois fois par jour et toilette à la chlorhexidine 4 % une fois par jour pendant <b>5 jours</b>. "
               "<b>Contrôle.</b> Trois séries de prélèvements sur des jours différents ; la première au moins <b>48 heures après la fin</b> de la décolonisation. Les précautions contact sont maintenues jusqu'à trois séries négatives.")]),
        ("Clostridioides difficile", [PP("Chambre individuelle avec sanitaires dédiés, lavage des mains à l'eau et au savon (la solution hydro-alcoolique est insuffisante), précautions contact jusqu'à 48 heures après la normalisation des selles.")]),
    ], lang="fr", extra_pages=4)
    # --- insulin
    protocol("PHA-INS-02_Inpatient_Insulin_Sliding_Scale_v3.pdf", "PHA-INS-02", "Inpatient Subcutaneous Insulin Sliding Scale", "3",
             "Diabetes Inpatient Team", D(2026, 3, 23), [
        ("Scale (insulin aspart, subcutaneous)", [
            TB(["Capillary glucose (mmol/L)", "Units of insulin aspart", "Note"],
               [("below 4.0", "0", "hypoglycaemia protocol"), ("4.0 to 7.9", "0", ""), ("8.0 to 11.9", "2", ""), ("12.0 to 15.9", "4", ""),
                ("16.0 to 19.9", "6", ""), ("20.0 or above", "8", "and call the doctor")], [60, 50, 60]),
            PP("Give the dose with the meal. Record the glucose value, the units given and initials on the insulin chart. A dose that differs from the scale is a medication incident unless the doctor has written an override.")]),
    ], extra_pages=1)
    # --- consent
    protocol("LEG-CON-01_Consent_to_Treatment_Policy_v4.pdf", "LEG-CON-01", "Consent to Treatment Policy", "4", "Medical Director", D(2026, 2, 2), [
        ("Valid consent", [PP("Consent must be given voluntarily by a patient with capacity after information on the procedure, its risks and alternatives. The form must name the "
                              "procedure and, for any procedure on paired organs or limbs, the side (right or left) in full.")]),
        ("Timing", [PP("The patient signs the form before any pre-medication is given and before transfer to the theatre suite. A form signed after pre-medication is not valid.")]),
        ("Discrepancy at the time of surgery", [PP("If the procedure or the side on the consent form differs from the planned or marked operative site, <b>the operation must not proceed</b>. "
                                                   "The surgeon stops the line, the team confirms the site with the patient, a new consent form is completed, and the discrepancy is reported "
                                                   "in the incident reporting system within 24 hours.")]),
    ], extra_pages=2)
    # --- discharge policy
    protocol("ADM-DIS-04_Discharge_and_Transfer_of_Care_Policy_v3.pdf", "ADM-DIS-04", "Discharge and Transfer of Care Policy", "3",
             "Director of Patient Flow", D(2026, 7, 6), [
        ("Discharge summary", [PP("A discharge summary is sent to the general practitioner (GP) on the day of discharge. It lists the medicines (new, changed, stopped), the follow-up arrangements and the "
                                  "investigations still pending.")]),
        ("Pending results", [PP("The consultant who discharged the patient remains responsible for results pending at discharge. <b>Every abnormal result finalised after discharge is "
                                "communicated to the GP within 2 working days of the date the result is finalised.</b> Working days are Monday to Friday. Normal results are filed without communication.")]),
        ("Follow-up", [PP("Follow-up appointments requested on the discharge summary are booked before discharge or, if clinic capacity does not allow, within 5 working days; a booking later than "
                          "the requested timeframe is escalated to the clinic manager.")]),
    ], extra_pages=2)
    # --- formulary
    rows = sorted([(n, s[0], s[1]) for n, s in S.FORMULARY_STATUS.items()])
    protocol("PHA-FOR-00_Hospital_Formulary_2026-2027.pdf", "PHA-FOR-00", "Hospital Formulary 2026-2027", "2026", "Drug and Therapeutics Committee",
             D(2026, 7, 1), [
        ("Status codes", [PP("<b>F</b> - formulary: may be prescribed by any authorised prescriber. <b>R</b> - restricted: initiation only by the named specialty; continuation by any prescriber. "
                            "<b>NF</b> - non-formulary: supplied only after individual patient approval by the Drug and Therapeutics Committee (D&amp;T); the approval states its validity period.")]),
        ("Formulary list", [TB(["Medicine", "Status", "Condition"], [list(r) for r in rows], [50, 20, 100])]),
    ], extra_pages=2)


# ------------------------------------------------------------------ patient documents
def narrative_en(p, rng, dx):
    return (f"{p.first} {p.last} is a {p.age_on(D(2026, 11, 10))}-year-old {'man' if p.sex == 'M' else 'woman'} admitted with {dx}. "
            f"{rng.choice(['Symptoms began three days before admission.', 'He or she had been unwell for about a week.', 'The onset was acute.'])} "
            f"{rng.choice(['There is no recent travel.', 'There were no sick contacts.', 'Oral intake had been poor.'])} "
            "Examination on admission was unremarkable apart from the findings listed below; investigations were requested as in the plan.")


def admission_note(p, d, dx, hx, meds, allergy, plan, lang=None, extra=(), fn=None, role="evidence"):
    lang = lang or p.lang
    f = lang == "fr"
    L = lambda en, fr: fr if f else en
    b = [H1(L("Admission note", "Observation d'admission")),
         demog(p, [(L("Admission date", "Date d'admission"), fd(d)), (L("Weight", "Poids"), f"{p.weight:g} kg".replace(".", ",") if f else f"{p.weight:g} kg"), (L("Ward", "Service"), p.ward)], on=d),
         H2(L("Presenting problem", "Motif d'hospitalisation")), PP(dx), H2(L("History", "Antécédents et histoire de la maladie")), PP(hx),
         H2(L("Allergies", "Allergies")), PP(allergy), H2(L("Medicines before admission", "Traitement avant l'admission")),
         TB([L("Medicine", "Médicament"), L("Dose", "Dose"), L("Frequency", "Fréquence")], meds, [70, 45, 55]) if meds else PP(L("None.", "Aucun.")),
         PB, H2(L("Examination", "Examen clinique")), PP(L("Alert and orientated. Chest clear. Abdomen soft and non-tender. No peripheral oedema. Heart sounds normal.",
                                                         "Patient consciente et orientée. Auscultation pulmonaire libre. Abdomen souple et indolore. Pas d'œdème des membres inférieurs. Bruits du cœur normaux.")),
         H2(L("Plan", "Conduite à tenir")), *[LI(x) for x in plan], *extra,
         PP(L("Admitting clinician: Dr Camille Vasseur, registrar.", "Médecin admetteur : Dr Camille Vasseur, interne."))]
    emit(fn or f"ADM_{slug(p.last)}_{slug(p.first)}_{d.isoformat()}.pdf", "admission_note", f"Admission note {p.name}", lang, b, d, p.key,
         banner=p.banner(), role=role)


def scenario_patient_docs():
    pd = P
    # ---- Delaunay: two lab reports
    p = pd["delaunay"]
    admission_note(p, D(2026, 11, 3), "Community-acquired pneumonia with reduced oral intake.",
                   "Seven days of productive cough and fever. Past history: hypertension, benign prostatic hyperplasia. Lives with his wife, independent.",
                   [("Amlodipine", "5 mg", "once daily"), ("Tamsulosin", "400 micrograms", "at night")], "No known drug allergies.",
                   ["Blood tests twice weekly", "Intravenous fluids, review in 48 hours", "Physiotherapy"])
    for d, req in ((D(2026, 11, 5), "Dr C. Vasseur"), (D(2026, 11, 12), "Dr C. Vasseur")):
        lab_pdf(p, d, S.LAB_DELAUNAY[d], req, p.ward, f"{fd(d)} 07:10")
    # ---- Ferrand
    p = pd["ferrand"]
    admission_note(p, D(2026, 11, 14), "Chute avec fracture du col fémoral droit, en attente d'une prise en charge orthopédique.",
                   "Patiente de 78 ans vivant seule, hypertension artérielle traitée, ostéoporose. Pas de diabète connu.",
                   [("Amlodipine", "5 mg", "1 fois par jour"), ("Oméprazole", "20 mg", "1 fois par jour"), ("Paracétamol", "1 g", "jusqu'à 4 fois par jour")],
                   "Aucune allergie médicamenteuse connue.", ["Thromboprophylaxie curative à adapter à la fonction rénale", "Bilan biologique quotidien", "Avis orthogériatrique"])
    for d in (S.FERRAND_DATE1, S.FERRAND_DATE2):
        panel = S.normal_panel(p, Creat=S.FERRAND_CREAT[d], Urea=9.8 if d == S.FERRAND_DATE1 else 7.2, K=4.6)
        lab_pdf(p, d, panel, "Dr C. Vasseur", p.ward, f"{fd(d)} 06:45", keys=[a[0] for a in S.ANALYTES if a[0] not in ("TSH", "Ferr")])
    # prescription chart: enoxaparin ordered, dose left blank -> the question asks for the dose
    b = [H1("Feuille de prescription"), demog(p, [("Date", fd(S.FERRAND_DATE1)), ("Poids", "62 kg (pesée du 14/11/2026)"), ("Allergies", "aucune connue")]),
         H2("Prescriptions actives"),
         TB(["Médicament", "Dose", "Voie", "Fréquence", "Prescripteur"],
            [("Enoxaparine", "à déterminer selon la fonction rénale", "SC", "voir protocole PHA-REN-02", "Dr Vasseur"), ("Amlodipine", "5 mg", "PO", "1 fois par jour", "Dr Vasseur"),
             ("Oméprazole", "20 mg", "PO", "1 fois par jour", "Dr Vasseur"), ("Paracétamol", "1 g", "PO", "jusqu'à 4 fois par jour", "Dr Vasseur")], [38, 56, 14, 40, 22]),
         PP("Aucune insuline ni antidiabétique n'est prescrit. Les examens biologiques demandés à l'admission figurent dans les comptes rendus du laboratoire.")]
    emit("PRESC_Ferrand_Odile_2026-11-16.pdf", "prescription", "Prescription chart Ferrand", "fr", b, S.FERRAND_DATE1, "ferrand", banner=p.banner(), role="evidence")
    # ---- Marchand
    p = pd["marchand"]
    admission_note(p, D(2026, 10, 30), "Décompensation cardiaque avec insuffisance rénale aiguë.",
                   "Dyspnée d'aggravation progressive, prise de poids de 4 kg en une semaine. Antécédents : hypertension, diabète de type 2, fibrillation atriale paroxystique.",
                   S.HOME_MEDS_MARCHAND, "Aucune allergie médicamenteuse connue.", ["Diurétiques intraveineux", "Surveillance du potassium et de la créatininémie", "Échocardiographie"])
    b = [H1("Compte rendu d'hospitalisation / courrier de sortie"),
         demog(p, [("Admission / sortie", f"{fd(D(2026, 10, 30))} / {fd(D(2026, 11, 9))}"), ("Médecin responsable", "Dr Antoine Leroy, cardiologue")]),
         H2("Diagnostic"), PP("Insuffisance cardiaque aiguë à fraction d'éjection préservée, insuffisance rénale aiguë résolue, fibrillation atriale."),
         H2("Évolution"), PP("Amélioration sous diurétiques intraveineux avec une perte de poids de 5 kg. La créatininémie est revenue à sa valeur de base. Une anticoagulation par apixaban a été débutée "
                             "après concertation avec le patient."), PB,
         H2("Traitement de sortie"),
         TB(["Médicament", "Dose", "Fréquence", "Statut"], [(n, d_, fr_, st) for n, d_, fr_, st, _ in S.DISCHARGE_MEDS_MARCHAND], [45, 30, 45, 40]),
         H2("Explication des modifications"),
         *[PP(f"<b>{n}</b> - {r}.") for n, d_, fr_, st, r in S.DISCHARGE_MEDS_MARCHAND if r],
         PB, H2("Suivi"), PP("Consultation de cardiologie dans 6 semaines. Médecin traitant : contrôle du ionogramme à une semaine."),
         PP("Examens en attente à la sortie : aucun.")]
    emit("CRH_Marchand_Helene_2026-11-09.pdf", "discharge_summary", "Discharge summary Marchand", "fr", b, D(2026, 11, 9), "marchand", banner=p.banner(), role="evidence")
    # ---- Lefebvre
    p = pd["lefebvre"]
    admission_note(p, D(2026, 11, 10), "Pneumonie communautaire de sévérité modérée.",
                   "Toux productive et fièvre depuis quatre jours. Antécédent d'asthme léger. Non-fumeur.",
                   [("Salbutamol inhaler", "100 micrograms", "when required")],
                   "<b>PENICILLIN - anaphylaxis (2009): facial angioedema, urticaria and hypotension requiring adrenaline.</b>",
                   ["Antibiotics according to the antibiotic policy", "Oxygen to keep SpO2 94-98%", "Chest X-ray"], lang="en")
    b = [H1("Inpatient drug chart"), demog(p, [("Date", fd(D(2026, 11, 10))), ("Weight", "88 kg"), ("Allergy status", "No known drug allergies (NKDA)")]),
         H2("Prescriptions"),
         TB(["Medicine", "Dose", "Route", "Frequency", "Start", "Stop"],
            [("Amoxicillin", "1 g", "PO", "three times daily", "10/11/2026", "11/11/2026"), ("Doxycycline", "200 mg then 100 mg", "PO", "once daily", "11/11/2026", ""),
             ("Salbutamol inhaler", "100 micrograms", "INH", "when required", "10/11/2026", "")], [38, 36, 14, 36, 24, 22]),
         H2("Administration record"),
         TB(["Medicine", "Date", "Time", "Given by"],
            [("Amoxicillin 1 g", "10/11/2026", "14:10", "Nurse A. Roche"), ("Amoxicillin 1 g", "10/11/2026", "22:05", "Nurse M. Dumas"),
             ("Amoxicillin 1 g", "11/11/2026", "06:00", "Nurse M. Dumas"), ("Doxycycline 200 mg", "11/11/2026", "09:00", "Nurse A. Roche")], [50, 36, 24, 50]),
         PP("11/11/2026 07:30 - Amoxicillin stopped by the ward pharmacist and replaced by doxycycline.")]
    emit("MAR_Lefebvre_Yves_2026-11-10.pdf", "drug_chart", "Inpatient drug chart Lefebvre", "en", b, D(2026, 11, 10), "lefebvre", banner=p.banner(), role="evidence")
    write_eml("2026-11-11_Pharmacist_intervention_Lefebvre_MRN-4483391.eml", "pharmacy.wards@ch-saint-aubin.example", "ward3b@ch-saint-aubin.example",
              dt.datetime(2026, 11, 11, 7, 41), "Pharmacist intervention - MRN 4483391 - antibiotic changed",
              "Dear Ward 3B team,\n\nDuring this morning's chart review I stopped amoxicillin for Mr Lefebvre (MRN 4483391) and recommended doxycycline.\n\n"
              "The allergy box on the drug chart reads NKDA, whereas the admission note records a penicillin anaphylaxis. I have asked the admitting doctor to correct the "
              "drug chart and I have filed an incident report.\n\nPlease monitor for any late reaction today.\n\nElodie Faure\nWard pharmacist, medicine", role="evidence", sender="Elodie Faure")
    # ---- Coste
    p = pd["coste"]
    b = [H1("Inpatient drug chart"), demog(p, [("Chart printed", "15/11/2026 08:00"), ("Weight", "76 kg"), ("Allergies", "none known")]),
         H2("Active prescriptions on 15/11/2026"), TB(["Medicine", "Dose and frequency", "Status"], [(n, d_, "ACTIVE") for n, d_ in S.COSTE_ACTIVE], [45, 100, 25]),
         H2("Discontinued prescriptions"),
         TB(["Medicine", "Dose and frequency", "Status"], [("Warfarin", "3 mg once daily", "STOPPED 10/11/2026 - atrial fibrillation now on apixaban plan"), ("Naproxen", "250 mg twice daily", "STOPPED 12/11/2026")], [45, 40, 85]),
         PP("Prescriber: Dr Maxime Perrot, cardiology registrar.")]
    emit("MAR_Coste_Raymond_2026-11-15.pdf", "drug_chart", "Inpatient drug chart Coste", "en", b, D(2026, 11, 15), "coste", banner=p.banner(), role="evidence")
    # ---- Perrin
    p = pd["perrin"]
    b = [H1("Dossier de la consultation d'anticoagulation"), demog(p, [("Indication", "fibrillation atriale"), ("INR cible", "2,0 - 3,0"), ("Traitement", "warfarine (comprimés de 2 mg)"),
                                                                       ("Dose hebdomadaire actuelle", "28 mg (4 mg par jour)")]),
         H2("Historique des INR"), TB(["Date", "INR", "Dose hebdomadaire à la date", "Observations"],
                                      [(fd(d), f"{v:.1f}".replace(".", ","), "28 mg", "") for d, v in S.PERRIN_INR] + [("20/10/2026", "2,2", "28 mg", "premier contrôle après stabilisation")][:0], [28, 20, 50, 70]),
         PP("La patiente est stable depuis septembre. Elle prend sa warfarine le soir. Aucun médicament interagissant n'a été ajouté. Le dernier prélèvement a été réalisé le 10/11/2026 à la consultation."),
         PB, H2("Éducation thérapeutique"), PP("Les règles d'alimentation (aliments riches en vitamine K), la conduite à tenir en cas d'oubli et les signes de saignement ont été rappelés. Un carnet de suivi a été remis.")]
    emit("INR_Perrin_Josiane_2026-11-10.pdf", "anticoag_record", "Anticoagulation record Perrin", "fr", b, D(2026, 11, 10), "perrin", banner=p.banner(), role="evidence")
    # ---- Blanc
    p = pd["blanc"]
    b = [H1("Carnet de vaccination - extrait du dossier"), demog(p, [("Édité le", fd(S.VACC_ASOF))]),
         TB(["Vaccin", "Date d'administration", "Lot"], [(n, fd(d), f"L{abs(hash(n)) % 90000 + 10000}"[:0] + f"{(i * 7919 + 10417) % 90000 + 10000}") for i, (n, d) in enumerate(S.BLANC_RECORD)], [80, 50, 40]),
         PP("Aucune autre vaccination n'est enregistrée dans le dossier hospitalier. Les vaccinations réalisées en ville ne sont pas reprises ici sauf si le patient a présenté son carnet papier, ce qui n'est pas le cas."),
         PP("Il n'y a aucune contre-indication vaccinale connue et aucune allergie documentée.")]
    emit("VAC_Blanc_Gerard_2026-11-20.pdf", "vaccination_record", "Vaccination record Blanc", "fr", b, S.VACC_ASOF, "blanc", banner=p.banner(), role="evidence")
    # ---- Roussel
    p = pd["roussel"]
    for d, mm_, comp in ((D(2026, 3, 14), 9, "Previous examination: none available at this hospital."), (D(2026, 11, 12), 12, "Comparison: CT chest of 14/03/2026, in which the right upper lobe nodule measured 9 mm.")):
        b = [H1("CT chest - radiology report"), demog(p, [("Examination date", fd(d)), ("Radiologist", "Dr Ines Carvalho")], on=d),
             H2("Technique and comparison"), PP("Volumetric CT of the chest without contrast, 1 mm reconstructions. " + comp),
             H2("Findings"), PP(f"Solid nodule of the right upper lobe, longest axial diameter {mm_} mm. A second solid nodule of the left lower lobe measures 4 mm and is unchanged from previous imaging. "
                                "No pleural effusion. No enlarged mediastinal or hilar lymph nodes. The visible upper abdomen is unremarkable."), PB,
             H2("Impression"), PP(f"Right upper lobe solid nodule, {mm_} mm. 4 mm left lower lobe nodule, stable. See the pulmonary nodule follow-up guideline for the recommended action."),
             PP("Report validated electronically.")]
        emit(f"CT_Chest_Roussel_Simone_{d.isoformat()}.pdf", "imaging_report", f"CT chest {p.name} {fd(d)}", "en", b, d, p.key, banner=p.banner(), role="evidence")
    # ---- Tessier
    p = pd["tessier"]
    t = S.TESSIER
    b = [H1("Anaesthetic record"), demog(p, [("Date of surgery", fd(t["date"])), ("Weight / height", "124 kg / 181 cm"), ("ASA grade", "II"), ("Anaesthetist", "Dr Valérie Huet")]),
         H2("Peri-operative timeline"),
         TB(["Time", "Event"], [("07:55", "Patient in anaesthetic room, monitors applied"), ("08:05", "Induction of general anaesthesia"), ("08:15", "Intubation, patient positioned"),
                                (t["given"], f"{t['abx']} {t['dose_g']} g intravenous"), ("08:45", "Surgical time-out completed"), (t["incision"], "Skin incision"), ("09:48", "End of surgery"),
                                ("10:05", "Extubation")], [25, 140]),
         PB, H2("Medicines given"), TB(["Medicine", "Dose", "Route", "Time"], [("Propofol", "250 mg", "IV", "08:05"), ("Fentanyl", "150 micrograms", "IV", "08:05"),
                                                                              (t["abx"], f"{t['dose_g']} g", "IV", t["given"]), ("Ondansetron", "4 mg", "IV", "09:40")], [45, 40, 20, 25]),
         PP("No intra-operative incident. Estimated blood loss 50 mL.")]
    emit("ANAES_Tessier_Bernard_2026-11-17.pdf", "anaesthetic_record", "Anaesthetic record Tessier", "en", b, t["date"], p.key, banner=p.banner(), role="evidence")
    b = [H1("Operation note"), demog(p, [("Date", fd(t["date"])), ("Surgeon", "Mr Olivier Brun")]), H2("Procedure"), PP("Laparoscopic cholecystectomy for symptomatic gallstones."),
         H2("Findings"), PP("Thick-walled gallbladder with adhesions to the omentum; the critical view of safety was obtained. No bile spillage."), PB,
         H2("Closure and plan"), PP("Port sites closed with absorbable sutures. Day-case pathway with discharge the same evening if recovery is uneventful. Antibiotic prophylaxis was given by the anaesthetist; see the anaesthetic record.")]
    emit("OPNOTE_Tessier_Bernard_2026-11-17.pdf", "operation_note", "Operation note Tessier", "en", b, t["date"], p.key, banner=p.banner(), role="evidence")
    # ---- Moreau
    p = pd["moreau"]
    admission_note(p, D(2026, 11, 16), "Amygdalectomie programmée, surveillance post-opératoire.", "Enfant en bonne santé, amygdalites à répétition (6 épisodes cette année). Vaccinations à jour.",
                   [], "Aucune allergie médicamenteuse connue.", ["Antalgiques selon le poids", "Retour à domicile à J1 si boit et mange"], lang="fr")
    b = [H1("Feuille de prescription pédiatrique"), demog(p, [("Date", fd(D(2026, 11, 16))), ("Poids mesuré", "14,5 kg"), ("Allergies", "aucune connue")]),
         H2("Prescriptions"), TB(["Médicament", "Dose", "Voie", "Fréquence", "Prescripteur"],
                                 [("Paracétamol suspension buvable", f"{S.MOREAU['prescribed_mg']} mg", "PO", f"toutes les {S.MOREAU['freq_h']} heures", "Dr Marchetti"),
                                  ("Ibuprofène suspension buvable", "100 mg", "PO", "toutes les 8 heures si douleur", "Dr Marchetti")], [56, 28, 14, 46, 26]),
         PP("Infirmière référente : Mme Aurélie Benoît. La famille a reçu la fiche d'information sur les antalgiques.")]
    emit("PRESC_Moreau_Lea_2026-11-16.pdf", "prescription", "Prescription chart Moreau", "fr", b, D(2026, 11, 16), "moreau", banner=p.banner(), role="evidence")
    # ---- Girard / Giraud
    g, h = pd["girard"], pd["giraud"]
    admission_note(g, D(2026, 11, 12), "Heart failure with acute kidney injury.", "Known heart failure with reduced ejection fraction, ischaemic heart disease and chronic kidney disease stage 3.",
                   [("Bisoprolol", "5 mg", "once daily"), ("Furosemide", "80 mg", "once daily")], "No known drug allergies.", ["Daily weights", "Renal function daily"])
    admission_note(h, D(2026, 11, 13), "Diarrhoea and dehydration with suspected acute kidney injury.", "Type 2 diabetes treated with metformin and a sulfonylurea; recent course of antibiotics for a chest infection.",
                   [("Metformin", "1 g", "twice daily"), ("Gliclazide", "80 mg", "twice daily")], "No known drug allergies.", ["Intravenous fluids", "Stop metformin", "Repeat U&E in 24 hours"])
    lab_pdf(g, D(2026, 11, 15), S.normal_panel(g, K=4.7, Urea=11.2, Creat=148, Alb=36), "Dr C. Vasseur", g.ward, "15/11/2026 07:00",
            keys=["Na", "K", "Cl", "Urea", "Creat", "CRP", "Alb", "Hb", "WBC", "Plt"])
    # the 16/11 report filed under Girard's name belongs to Giraud
    panel = S.normal_panel(h, Na=131, K=6.1, Urea=19.4, Creat=214, CRP=58, Hb=121)
    fn = "LAB_Girard_Henri_2026-11-16.pdf"
    blocks = lab_blocks(h, D(2026, 11, 16), panel, "Dr C. Vasseur", h.ward, "16/11/2026 07:05", keys=["Na", "K", "Cl", "Urea", "Creat", "CRP", "Alb", "Hb", "WBC", "Plt"],
                        final_note="CRITICAL VALUE: potassium 6.1 mmol/L telephoned to the ward on 16/11/2026 at 10:42.")
    emit(fn, "lab_report", "Laboratory report 16/11/2026", "en", blocks, D(2026, 11, 16), "giraud", banner=h.banner(), role="evidence")
    # ---- Robert (consent scanned + operation note)
    p = pd["robert"]
    b = [H1("Formulaire de consentement à un acte chirurgical"), demog(p, [("Date", "18/11/2026")]),
         KV([("Intervention proposée", "Arthroscopie du genou DROIT"), ("Chirurgien", "Dr Anselme Vidal"), ("Anesthésie", "générale")]),
         PP("J'ai reçu une information claire sur l'intervention, ses risques et les alternatives. J'ai pu poser mes questions. J'accepte l'intervention proposée."),
         SP(6), KV([("Signature du patient", "Michel Robert - signé le 18/11/2026 à 07:45"), ("Signature du chirurgien", "Dr A. Vidal - signé le 18/11/2026 à 07:50")])]
    emit("SCAN_20261118_0802.pdf", "consent_form", "Consent form (scanned)", "fr", b, D(2026, 11, 18), "robert", scanned=True, role="evidence")
    b = [H1("Compte rendu opératoire"), demog(p, [("Date", "18/11/2026"), ("Chirurgien", "Dr Anselme Vidal"), ("Prémédication administrée", "08:30"), ("Début de l'intervention", "09:10")]),
         H2("Intervention réalisée"), PP("Arthroscopie du genou GAUCHE avec méniscectomie partielle interne."), H2("Site opératoire"), PP("Marquage du site : genou gauche, vérifié à l'arrivée au bloc."),
         PB, H2("Suites"), PP("Appui autorisé d'emblée. Sortie le lendemain. Contrôle clinique à 15 jours.")]
    emit("CRO_Robert_Michel_2026-11-18.pdf", "operation_note", "Operation note Robert", "fr", b, D(2026, 11, 18), "robert", banner=p.banner(), role="evidence")
    # ---- Guérin MAR
    p = pd["guerin"]
    admission_note(p, D(2026, 11, 3), "Pneumonie sévère de la base droite.", "Fièvre à 39,4 °C, dyspnée et douleur thoracique depuis 48 heures. Aucun antécédent notable.", [], "Aucune allergie médicamenteuse connue.",
                   ["Ceftriaxone intraveineuse selon la politique antibiotique", "Réévaluation à 48-72 heures"], lang="fr")
    rows = [(fd(d), "18:00", c, {"G": "A. Dubois", "N": "-"}[c], S.GUERIN_N_REASON if c == "N" else "") for d, c in S.GUERIN_DOSES]
    b = [H1("Medication administration record"), demog(p, [("Prescription", "Ceftriaxone 2 g IV once daily, from 03/11/2026"), ("Indication", "severe CAP"), ("Allergies", "none known")]),
         H2("Administration - ceftriaxone 2 g IV"), TB(["Date", "Scheduled", "Code", "Given by", "Comment"], rows, [28, 22, 14, 30, 76]),
         SM("Code G = given, N = not given. No oral switch was documented during this period."), PB,
         H2("Other medicines"), TB(["Medicine", "Dose", "Frequency"], [("Paracetamol", "1 g", "up to four times daily"), ("Enoxaparin", "40 mg", "once daily")], [60, 40, 60])]
    emit("MAR_Guerin_Anne-Sophie_2026-11-03.pdf", "drug_chart", "Medication administration record Guérin", "en", b, D(2026, 11, 3), "guerin", banner=p.banner(), role="evidence")
    # ---- Benali
    p = pd["benali"]
    b = [H1("Discharge summary"), demog(p, [("Admission / discharge", f"10/11/2026 / {fd(S.BENALI_DISCHARGE)}"), ("Consultant", "Dr Hélène Roux"), ("GP", "Dr Pascal Garnier")]),
         H2("Diagnosis"), PP("Pyelonephritis treated with intravenous then oral antibiotics; fatigue under investigation."),
         H2("Course"), PP("Fever settled within 48 hours. Renal ultrasound normal. Fatigue and weight gain prompted thyroid and vitamin D testing on the day before discharge."), PB,
         H2("Results pending at discharge"), TB(["Test", "Sample date"], [(n, "11/11/2026") for n, _, _, _ in S.BENALI_PENDING], [100, 40]),
         PP("The discharging consultant remains responsible for these results (see the discharge and transfer of care policy)."),
         H2("Medicines on discharge"), TB(["Medicine", "Dose", "Duration"], [("Cefalexin", "500 mg three times daily", "until 17/11/2026")], [60, 70, 40])]
    emit("CRH_Benali_Nadia_2026-11-12.pdf", "discharge_summary", "Discharge summary Benali", "en", b, S.BENALI_DISCHARGE, p.key, banner=p.banner(), role="evidence")
    lab_pdf(p, D(2026, 11, 13), {}, "Dr H. Roux", p.ward, "11/11/2026 15:20", keys=[], extra_rows=[
        ("TSH", "9.80", "mIU/L", "0.40 - 4.00", "H"), ("25-OH vitamin D", "38", "nmol/L", "50 - 125", "L")],
        final_note="Final report issued 13/11/2026 (samples of 11/11/2026).")
    b = [H1("Microbiology report"), demog(p, [("Sample", "blood culture, set 2, 11/11/2026"), ("Final report", "17/11/2026")]),
         TB(["Test", "Result"], [("Blood culture, set 2", "no growth at 5 days")], [60, 100]), SM("Final report. No further testing planned.")]
    emit("MICRO_Benali_Nadia_2026-11-17.pdf", "microbiology", "Microbiology Benali", "en", b, D(2026, 11, 17), p.key, banner=p.banner(), role="evidence")
    # ---- Martel
    p = pd["martel"]
    b = [H1("Discharge summary"), demog(p, [("Admission / discharge", f"02/11/2026 / {fd(S.MARTEL_DISCHARGE)}"), ("Consultant", "Dr Antoine Leroy")]),
         H2("Diagnosis"), PP("Non-ST-elevation myocardial infarction treated by coronary angiography and stenting of the circumflex artery."),
         H2("Course"), PP("Uncomplicated recovery. Dual antiplatelet therapy started; statin and beta-blocker optimised."), PB,
         H2("Follow-up required"), TB(["Follow-up", "Requested timeframe"], [(n, t) for n, _, t in S.MARTEL_REQUIRED], [90, 60]),
         PP("The timeframes run from the day of discharge. Appointments are booked by the cardiology secretariat."),
         H2("Medicines on discharge"), TB(["Medicine", "Dose"], [("Aspirin", "75 mg once daily"), ("Ticagrelor", "90 mg twice daily"), ("Atorvastatin", "80 mg at night"), ("Bisoprolol", "2.5 mg once daily")], [70, 70])]
    emit("CRH_Martel_Jacques_2026-11-06.pdf", "discharge_summary", "Discharge summary Martel", "en", b, S.MARTEL_DISCHARGE, p.key, banner=p.banner(), role="evidence")
    # ---- Fabre obs chart
    p = pd["fabre"]
    hdr = ["Heure", "FR (/min)", "SpO2 (%)", "O2", "TA syst. (mmHg)", "Pouls (/min)", "Conscience", "T (°C)"]
    rows = [(t, str(rr), str(sp), "oxygène" if o2 else "air", str(sbp), str(hr), "alerte" if al else "confus", f"{tp:.1f}".replace(".", ",")) for t, rr, sp, o2, sbp, hr, al, tp in S.FABRE_OBS]
    b = [H1("Feuille de surveillance - constantes"), demog(p, [("Date", fd(S.FABRE_DATE)), ("Motif", "pneumopathie, surveillance rapprochée")]),
         TB(hdr, rows, [16, 20, 20, 20, 30, 24, 24, 16], align="lrrlrrll"), PB,
         H2("Transmissions infirmières"), PP("03:00 - toux plus fréquente, patient calme. 06:00 - oxygène 2 L/min débuté, fatigue. 09:00 - fébrile, hydratation encouragée. 12:00 - amélioration, mange son repas.")]
    emit("OBS_Fabre_Louis_2026-11-15.pdf", "observation_chart", "Observation chart Fabre", "fr", b, S.FABRE_DATE, p.key, banner=p.banner(), role="evidence")
    # ---- Renard insulin chart (scan)
    p = pd["renard"]
    b = [H1("Insulin sliding scale chart"), demog(p, [("Date", "10/11/2026"), ("Insulin", "aspart subcutaneous per protocol PHA-INS-02"), ("Diagnosis", "type 2 diabetes, cellulitis")]),
         TB(["Time", "Glucose (mmol/L)", "Units given", "Initials"], [(t, f"{g:.1f}", str(u), ini) for (t, g, u), ini in zip(S.RENARD, ("AR", "AR", "MD", "MD"))], [30, 40, 35, 30]),
         PP("No doctor's override is written on the chart.")]
    emit("SCAN_20261110_1904.pdf", "insulin_chart", "Insulin chart (scanned)", "en", b, D(2026, 11, 10), "renard", scanned=True, role="evidence")
    # ---- Caron
    p = pd["caron"]
    b = [H1("Inpatient prescription chart"), demog(p, [("Chart printed", fd(S.CARON_ASOF)), ("Weight", "73 kg"), ("Allergies", "none known")]),
         TB(["Medicine", "Dose and frequency", "Prescriber"], [(n, d_, "Dr Vasseur") for n, d_ in S.CARON_CHART], [55, 80, 35]), PB,
         PP("Indication of the heart failure regimen: hyponatraemia and heart failure with reduced ejection fraction. Review by cardiology on 20/11/2026.")]
    emit("MAR_Caron_Sylvie_2026-11-18.pdf", "drug_chart", "Prescription chart Caron", "en", b, S.CARON_ASOF, p.key, banner=p.banner(), role="evidence")
    a = S.CARON_APPROVAL
    write_eml("2026-11-16_DT_approval_tolvaptan_MRN-4486603.eml", "dt.committee@ch-saint-aubin.example", "pharmacy.wards@ch-saint-aubin.example",
              dt.datetime(2026, 11, 16, 16, 12), "D&T individual patient approval - tolvaptan - MRN 4486603",
              f"Dear colleagues,\n\nThe Drug and Therapeutics Committee approves tolvaptan 15 mg once daily for Ms Caron (MRN 4486603), non-formulary, for {a['days']} days, "
              f"from {fd(a['start'])} to {fd(a['start'] + dt.timedelta(days=a['days'] - 1))} inclusive. Any continuation requires a new request.\n\nNo approval has been requested for any other non-formulary or restricted medicine for this patient.\n\n"
              f"{a['approver']}", role="evidence", sender="Dr Élise Maurel")
    # ---- Ward 4B list
    b = [H1("MRSA screening - Ward 4B - situation at 14/11/2026"),
         TB(["Bed", "Patient", "Origin", "Bed type", "MRSA screen"], [list(r) for r in S.WARD4B], [20, 40, 62, 28, 28]),
         SM("Screen results are those available in the laboratory system at 14/11/2026 18:00. Pending = sample taken, result not yet available.")]
    emit("IPC_MRSA_screening_Ward4B_2026-11-14.pdf", "screening_list", "MRSA screening list Ward 4B", "en", b, D(2026, 11, 14), role="evidence")


# ------------------------------------------------------------------ appointments export, filler and noise
FIRST = ["Adèle", "Baptiste", "Chloé", "Damien", "Émilie", "Fabien", "Gaëlle", "Hugo", "Inès", "Julien", "Karine", "Lucas", "Manon", "Nicolas", "Océane", "Paul",
         "Quentin", "Rose", "Sébastien", "Théo", "Ursule", "Victor", "Wendy", "Yann", "Zoé"]
LAST = ["Aubry", "Bouvier", "Chevalier", "Deschamps", "Étienne", "Fontaine", "Gauthier", "Hubert", "Joubert", "Lacroix", "Maillard", "Noël", "Olivier", "Pasquier", "Rey",
        "Salmon", "Tanguy", "Vidal", "Weber", "Yvon", "Barre", "Collet", "Dupuy", "Evrard", "Gilles"]
DX = ["urinary tract infection", "cellulitis of the lower leg", "COPD exacerbation", "acute pancreatitis", "diverticulitis", "syncope", "hip fracture", "asthma exacerbation",
      "gastroenteritis", "deep vein thrombosis", "heart failure", "pneumonia"]


def appointments_export():
    rng = random.Random(77)
    rows = []
    clin = ["Cardiology clinic", "Diabetes clinic", "Respiratory clinic", "Orthopaedic fracture clinic", "Dermatology", "ENT clinic", "Rheumatology", "Cardiac rehabilitation assessment", "Echocardiography"]
    for i in range(58):
        d = D(2026, 11, 19) + dt.timedelta(days=rng.randint(1, 45))
        while d.weekday() > 4:
            d += dt.timedelta(days=1)
        rows.append((f"{rng.choice(LAST)} {rng.choice(FIRST)}", str(4400000 + rng.randint(10000, 99999)), rng.choice(clin), fd(d), f"{rng.randint(8, 16):02d}:{rng.choice(['00', '20', '40'])}"))
    m = P["martel"]
    for name, d in S.MARTEL_BOOKED.items():
        rows.append((f"{m.last.upper()} {m.first}", m.mrn, name, fd(d), "10:20" if "Cardiology" in name else "14:00"))
    rows.sort(key=lambda r: (r[0]))
    b = [H1("Outpatient clinic bookings - export of 19/11/2026"), SM("All bookings from 20/11/2026 onwards, sorted by patient name."),
         TB(["Patient", "MRN", "Clinic / examination", "Date", "Time"], [list(r) for r in rows], [55, 28, 70, 28, 20])]
    emit("Clinic_Bookings_Export_2026-11-19.pdf", "booking_export", "Clinic bookings export", "en", b, D(2026, 11, 19), role="evidence")


def filler_patients():
    rng = random.Random(2026)
    names = set()
    for i in range(14):
        while True:
            ln, fn_ = rng.choice(LAST), rng.choice(FIRST)
            if (ln, fn_) not in names and ln not in {p.last for p in P.values()}:
                names.add((ln, fn_))
                break
        sex = rng.choice("MF")
        dob = D(rng.randint(1938, 1998), rng.randint(1, 12), rng.randint(1, 28))
        key = f"fill{i}"
        P[key] = S.Patient(key, ln, fn_, sex, dob, str(4500000 + rng.randint(1000, 99999)), rng.choice(["en", "fr"]), float(rng.randint(52, 98)), rng.choice(["Medicine 3A", "Medicine 3B", "Surgery 2B"]))
        p = P[key]
        d = D(2026, 11, rng.randint(2, 13))
        dx = rng.choice(DX)
        panel = S.normal_panel(p, CRP=rng.choice([2, 14, 47]), Creat=int(S.rng_of(p, "Creat")[0] + rng.randint(5, 40)), Na=rng.randint(137, 143), K=round(rng.uniform(3.8, 4.8), 1),
                               Hb=int(S.rng_of(p, "Hb")[0] + rng.randint(2, 25)), WBC=round(rng.uniform(5, 12.5), 1))
        admission_note(p, d, dx.capitalize() + ".", narrative_en(p, rng, dx), [("Paracetamol", "1 g", "when required")], "No known drug allergies." if p.lang == "en" else "Aucune allergie médicamenteuse connue.",
                       ["Observations four times daily", "Blood tests as per ward round"], lang="en" if p.lang == "en" else "fr", role="filler")
        lab_pdf(p, d + dt.timedelta(days=1), panel, "Dr C. Vasseur", p.ward, f"{fd(d + dt.timedelta(days=1))} 07:00")
        # lab_pdf labels evidence; re-label as filler
        MANIFEST[-1]["role"] = "filler"
        b = [H1("Discharge summary" if p.lang == "en" else "Courrier de sortie"), demog(p, [("Admission / discharge", f"{fd(d)} / {fd(d + dt.timedelta(days=rng.randint(3, 8)))}")]),
             H2("Diagnosis"), PP(dx.capitalize() + ", treated on the ward with a good response."), H2("Course"), PP(narrative_en(p, rng, dx)), PB,
             H2("Medicines on discharge"), TB(["Medicine", "Dose"], [("Paracetamol", "1 g when required")], [70, 70]), H2("Follow-up"),
             PP("GP review in two weeks. No investigations pending at discharge.")]
        emit(f"DS_{slug(p.last)}_{slug(p.first)}_{d.isoformat()}.pdf", "discharge_summary", f"Discharge summary {p.name}", "en", b, d + dt.timedelta(days=5), key, banner=p.banner())


def noise_documents():
    topics = [
        ("FIRE-SAF-01_Fire_Safety_Procedure_v5.pdf", "Fire Safety Procedure", "FIRE-SAF-01", "Fire Safety Officer", 8),
        ("IT-DOW-02_Downtime_Procedure_Electronic_Record_v2.pdf", "Electronic Record Downtime Procedure", "IT-DOW-02", "Head of Digital Health", 5),
        ("HR-ROTA-2026-11_Medical_Staffing_Rota_November_2026.pdf", "Medical Staffing Rota, November 2026", "HR-ROTA", "Medical Staffing Office", 4),
        ("EST-VIS-01_Visitor_and_Parking_Guide_2026.pdf", "Visitor and Parking Guide 2026", "EST-VIS-01", "Estates and Facilities", 3),
        ("QUA-ACC-2026_Laboratory_Accreditation_Summary.pdf", "Laboratory Accreditation Summary", "QUA-ACC", "Laboratory Quality Manager", 4),
        ("DIR-RA-2025_Annual_Activity_Report_2025.pdf", "Annual Activity Report 2025", "DIR-RA-2025", "Directorate", 12),
        ("COM-PLN-03_Complaints_Handling_Procedure_v4.pdf", "Complaints Handling Procedure", "COM-PLN-03", "Patient Experience Team", 5),
        ("CAT-MEN-2026-11_Patient_Menu_Cycle_November_2026.pdf", "Patient Menu Cycle, November 2026", "CAT-MEN", "Catering Manager", 3),
        ("SEC-CYB-01_Cybersecurity_Awareness_Guide_v2.pdf", "Cybersecurity Awareness Guide", "SEC-CYB-01", "Information Security Officer", 5),
        ("RAD-MRI-01_MRI_Safety_Screening_Procedure_v3.pdf", "MRI Safety Screening Procedure", "RAD-MRI-01", "Radiology Superintendent", 5),
        ("NUR-FAL-02_Falls_Prevention_Policy_v4.pdf", "Falls Prevention Policy", "NUR-FAL-02", "Falls Prevention Group", 6),
        ("NUR-PRE-01_Pressure_Ulcer_Prevention_v3.pdf", "Pressure Ulcer Prevention", "NUR-PRE-01", "Tissue Viability Nurse", 6),
        ("HYG-LIN-01_Linen_and_Waste_Management_v3.pdf", "Linen and Waste Management", "HYG-LIN-01", "Hotel Services", 4),
        ("TRN-MAN-2026_Mandatory_Training_Matrix_2026.pdf", "Mandatory Training Matrix 2026", "TRN-MAN", "Learning and Development", 3)]
    for fn, title, code, owner, extra in topics:
        body = [PP("This document describes the arrangements in force at the Centre Hospitalier Saint-Aubin for the topic named in its title. It does not contain clinical dosing, results or "
                   "patient-specific information. Staff are asked to consult the relevant clinical protocols for patient care decisions.")]
        protocol(fn, code, title, "2", owner, D(2026, 2, 9), [("Overview", body), ("Arrangements", [PP("Responsibilities are shared between the department concerned, the ward managers and the directorate. "
                                                                                                          "Operational details are held by the document owner.")])], extra_pages=extra, role="filler")
    write_eml("2026-11-04_Training_reminder_mandatory_modules.eml", "learning@ch-saint-aubin.example", "all-staff@ch-saint-aubin.example", dt.datetime(2026, 11, 4, 9, 0),
              "Reminder: mandatory training modules due by 30 November", "Dear colleagues,\n\nPlease complete your mandatory training modules (fire safety, information governance, manual handling) before 30 November 2026.\n\nLearning and Development")
    write_eml("2026-11-09_Pharmacy_stock_notice_IV_fluids.eml", "pharmacy.stores@ch-saint-aubin.example", "wards@ch-saint-aubin.example", dt.datetime(2026, 11, 9, 14, 30),
              "Stock notice: temporary shortage of 500 mL sodium chloride bags", "Dear ward teams,\n\nA supplier delay affects 500 mL sodium chloride 0.9% bags. 1 litre bags remain available and are being allocated to the wards. "
              "Please do not stockpile.\n\nPharmacy stores")
    write_eml("2026-11-13_Ward_meeting_invitation_3A.eml", "ward3a.manager@ch-saint-aubin.example", "ward3a@ch-saint-aubin.example", dt.datetime(2026, 11, 13, 11, 5),
              "Ward 3A team meeting, Thursday 26 November", "Hello everyone,\n\nThe monthly team meeting for Ward 3A will take place on Thursday 26 November at 14:00 in the seminar room.\n\nAgenda: staffing, audit results, Christmas rota.\n\nClaire Dufour, ward manager")
    write_eml("2026-11-18_IT_maintenance_notice_weekend.eml", "servicedesk@ch-saint-aubin.example", "all-staff@ch-saint-aubin.example", dt.datetime(2026, 11, 18, 16, 45),
              "Planned maintenance of the electronic record, Saturday 21 November", "Dear colleagues,\n\nThe electronic patient record will be in read-only mode on Saturday 21 November from 06:00 to 09:00 for planned maintenance. The downtime procedure applies.\n\nIT Service Desk")
    write_eml("2026-11-10_Referral_acknowledgement_physiotherapy.eml", "physio.referrals@ch-saint-aubin.example", "ward3a@ch-saint-aubin.example", dt.datetime(2026, 11, 10, 10, 20),
              "Physiotherapy referral received", "Your physiotherapy referral has been received and will be triaged within two working days.\n\nPhysiotherapy department")
    write_eml("2026-11-12_Carte_cadeau_depart_Mme_Fabry.eml", "cadres.sante@ch-saint-aubin.example", "poste4@ch-saint-aubin.example", dt.datetime(2026, 11, 12, 8, 55),
              "Départ en retraite de Mme Fabry - participation", "Bonjour à toutes et tous,\n\nUne cagnotte est ouverte pour le départ en retraite de Mme Fabry (secrétariat de cardiologie). Merci de votre participation avant le 20 novembre.\n\nLes cadres de santé", lang="fr")


def probe():
    PROBE.mkdir(parents=True, exist_ok=True)
    b = [H1("Anticoagulation clinic record"), KV([("Patient", "LAMBERT Zoé"), ("Date of birth", "02/08/1969"), ("Hospital", "Hôpital des Cèdres (another institution)")]),
         TB(["Date", "INR"], [("02/11/2026", "4.6"), ("09/11/2026", "2.8")], [40, 30]), PP("Target INR 2.0 - 3.0. Warfarin 21 mg per week.")]
    emit("probe_doc_001.pdf", "probe", "Probe document", "en", b, D(2026, 11, 9), out_dir=PROBE)


def main():
    for d in (DOCS, OCR, PROBE):
        if d.exists():
            shutil.rmtree(d)
    CORPUS.mkdir(parents=True, exist_ok=True)
    hospital_documents()
    scenario_patient_docs()
    appointments_export()
    filler_patients()
    noise_documents()
    probe()
    MANIFEST.sort(key=lambda m: m["filename"])
    man = dict(name="CareBench V1 corpus", hospital=K.HOSPITAL, n_documents=len(MANIFEST), total_pages=sum(m["pages"] for m in MANIFEST),
               n_scanned=sum(m["scanned"] for m in MANIFEST), documents=MANIFEST)
    (CORPUS / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), "utf-8")
    h = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    (CORPUS / "FROZEN.json").write_text(json.dumps(dict(manifest_sha256=h, n_documents=len(MANIFEST), total_pages=man["total_pages"], generator="tools/corpus.py"), indent=1), "utf-8")
    print(f"{len(MANIFEST)} documents, {man['total_pages']} pages, {man['n_scanned']} scans")


if __name__ == "__main__":
    main()
