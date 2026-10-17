"""CareBench world model: one fictional hospital (Centre Hospitalier Saint-Aubin), November 2026.

Every fact a question depends on is defined here once and computed (eGFR, NEWS2, doses, dates, counts); `corpus.py`
prints the documents from these objects and `build_dataset.py` writes the expected answers from the same objects, so a
document and its answer cannot drift apart. All people, identifiers and institutions are fictional.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

D = dt.date


def fd(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


def add_business_days(d: dt.date, n: int) -> dt.date:
    while n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


@dataclass
class Patient:
    key: str
    last: str
    first: str
    sex: str
    dob: dt.date
    mrn: str
    lang: str = "en"
    weight: float | None = None
    ward: str = ""

    @property
    def name(self):
        return f"{self.last.upper()} {self.first}"

    def age_on(self, d: dt.date) -> int:
        return d.year - self.dob.year - ((d.month, d.day) < (self.dob.month, self.dob.day))

    def banner(self):
        return f"{self.name}  |  DOB {fd(self.dob)} ({self.sex})  |  MRN {self.mrn}" + (f"  |  {self.ward}" if self.ward else "")


P = {p.key: p for p in [
    Patient("delaunay", "Delaunay", "Marc", "M", D(1955, 6, 21), "4471823", "en", 81.0, "Medicine 3A"),
    Patient("ferrand", "Ferrand", "Odile", "F", D(1948, 2, 9), "4480110", "fr", 62.0, "Gériatrie 2C"),
    Patient("marchand", "Marchand", "Hélène", "F", D(1962, 9, 30), "4476652", "fr", 71.5, "Medicine 3A"),
    Patient("lefebvre", "Lefebvre", "Yves", "M", D(1973, 4, 12), "4483391", "en", 88.0, "Medicine 3B"),
    Patient("coste", "Coste", "Raymond", "M", D(1944, 11, 2), "4469047", "en", 76.0, "Cardiology 4A"),
    Patient("perrin", "Perrin", "Josiane", "F", D(1950, 12, 5), "4472260", "fr", 66.0, "Outpatient"),
    Patient("blanc", "Blanc", "Gérard", "M", D(1959, 3, 18), "4490518", "fr", 84.0, "Outpatient"),
    Patient("roussel", "Roussel", "Simone", "F", D(1957, 7, 14), "4465730", "en", 64.0, "Outpatient"),
    Patient("tessier", "Tessier", "Bernard", "M", D(1968, 1, 25), "4487715", "en", 124.0, "Surgery 2B"),
    Patient("moreau", "Moreau", "Léa", "F", D(2022, 5, 17), "4492206", "fr", 14.5, "Paediatrics 1A"),
    Patient("girard", "Girard", "Henri", "M", D(1951, 3, 14), "5502144", "en", 79.0, "Medicine 3B"),
    Patient("giraud", "Giraud", "Henri", "M", D(1957, 3, 14), "5502414", "en", 92.0, "Medicine 3A"),
    Patient("robert", "Robert", "Michel", "M", D(1960, 8, 8), "4488023", "fr", 85.0, "Surgery 2B"),
    Patient("guerin", "Guérin", "Anne-Sophie", "F", D(1979, 10, 10), "4491174", "fr", 58.0, "Medicine 3B"),
    Patient("benali", "Benali", "Nadia", "F", D(1985, 2, 20), "4474409", "en", 67.0, "Medicine 3A"),
    Patient("martel", "Martel", "Jacques", "M", D(1952, 5, 29), "4468815", "en", 90.0, "Cardiology 4A"),
    Patient("fabre", "Fabre", "Louis", "M", D(1940, 1, 9), "4459382", "fr", 70.0, "Geriatrics 2C"),
    Patient("renard", "Renard", "Paul", "M", D(1961, 4, 4), "4481950", "en", 95.0, "Medicine 3B"),
    Patient("caron", "Caron", "Sylvie", "F", D(1966, 12, 20), "4486603", "en", 73.0, "Medicine 3A"),
]}

# ------------------------------------------------------------------ laboratory
# key, English, French, unit, (low, high) male, (low, high) female, decimals
ANALYTES = [
    ("Na", "Sodium", "Sodium", "mmol/L", (136, 145), (136, 145), 0),
    ("K", "Potassium", "Potassium", "mmol/L", (3.5, 5.0), (3.5, 5.0), 1),
    ("Cl", "Chloride", "Chlorure", "mmol/L", (98, 107), (98, 107), 0),
    ("Urea", "Urea", "Urée", "mmol/L", (2.5, 7.8), (2.5, 7.8), 1),
    ("Creat", "Creatinine", "Créatinine", "µmol/L", (60, 110), (45, 90), 0),
    ("Gluc", "Glucose (fasting)", "Glycémie à jeun", "mmol/L", (3.9, 5.8), (3.9, 5.8), 1),
    ("CRP", "C-reactive protein", "Protéine C-réactive", "mg/L", (0, 5), (0, 5), 0),
    ("ALT", "ALT", "ALAT", "U/L", (7, 40), (7, 35), 0),
    ("AST", "AST", "ASAT", "U/L", (10, 40), (10, 35), 0),
    ("ALP", "Alkaline phosphatase", "Phosphatases alcalines", "U/L", (40, 130), (35, 120), 0),
    ("GGT", "Gamma-GT", "Gamma-GT", "U/L", (10, 71), (6, 42), 0),
    ("Bili", "Bilirubin, total", "Bilirubine totale", "µmol/L", (3, 21), (3, 21), 0),
    ("Alb", "Albumin", "Albumine", "g/L", (35, 50), (35, 50), 0),
    ("Ca", "Calcium (total)", "Calcium total", "mmol/L", (2.20, 2.60), (2.20, 2.60), 2),
    ("Mg", "Magnesium", "Magnésium", "mmol/L", (0.70, 1.05), (0.70, 1.05), 2),
    ("PO4", "Phosphate", "Phosphate", "mmol/L", (0.80, 1.50), (0.80, 1.50), 2),
    ("TSH", "TSH", "TSH", "mIU/L", (0.40, 4.00), (0.40, 4.00), 2),
    ("Ferr", "Ferritin", "Ferritine", "µg/L", (30, 400), (15, 150), 0),
    ("Hb", "Haemoglobin", "Hémoglobine", "g/L", (130, 175), (120, 155), 0),
    ("Hct", "Haematocrit", "Hématocrite", "L/L", (0.40, 0.52), (0.36, 0.46), 2),
    ("MCV", "MCV", "VGM", "fL", (80, 100), (80, 100), 0),
    ("WBC", "White cell count", "Leucocytes", "10^9/L", (4.0, 10.0), (4.0, 10.0), 1),
    ("Plt", "Platelets", "Plaquettes", "10^9/L", (150, 400), (150, 400), 0),
]
AN = {a[0]: a for a in ANALYTES}
HAEM = ("Hb", "Hct", "MCV", "WBC", "Plt", "Ferr")


def rng_of(p: Patient, key: str):
    a = AN[key]
    return a[4] if p.sex == "M" else a[5]


def flag(p: Patient, key: str, v: float) -> str:
    lo, hi = rng_of(p, key)
    return "L" if v < lo else "H" if v > hi else ""


def fmt_val(key: str, v: float, lang: str = "en") -> str:
    s = f"{v:.{AN[key][6]}f}"
    return s.replace(".", ",") if lang == "fr" else s


def fmt_range(key: str, p: Patient, lang: str = "en") -> str:
    lo, hi = rng_of(p, key)
    d = AN[key][6]
    f = (lambda x: f"{x:.{d}f}".replace(".", ",")) if lang == "fr" else (lambda x: f"{x:.{d}f}")
    return f"{f(lo)} - {f(hi)}"


NORMAL_M = dict(Na=140, K=4.2, Cl=102, Urea=5.4, Creat=88, Gluc=5.1, CRP=2, ALT=28, AST=24, ALP=82, GGT=34, Bili=11,
                Alb=42, Ca=2.38, Mg=0.86, PO4=1.12, TSH=1.8, Ferr=140, Hb=146, Hct=0.44, MCV=90, WBC=6.8, Plt=250)
NORMAL_F = dict(NORMAL_M, Creat=68, ALT=22, AST=21, ALP=74, GGT=22, Hb=132, Hct=0.40, Ferr=70)


def normal_panel(p: Patient, **over):
    base = dict(NORMAL_M if p.sex == "M" else NORMAL_F)
    base.update(over)
    return base


LAB_DELAUNAY = {
    D(2026, 11, 5): normal_panel(P["delaunay"], K=4.9, Urea=8.4, Creat=121, CRP=96, ALT=38, Alb=33, Hb=122, WBC=13.5, Plt=150, Mg=0.70),
    D(2026, 11, 12): normal_panel(P["delaunay"], K=5.4, Urea=9.6, Creat=128, CRP=38, ALT=52, Alb=31, Hb=118, WBC=11.8, Plt=164, Mg=0.72),
}


def abnormal(p: Patient, panel: dict) -> dict[str, str]:
    return {k: flag(p, k, v) for k, v in panel.items() if flag(p, k, v)}


# ------------------------------------------------------------------ renal function
def ckd_epi_2021(creat_umol: float, age: int, female: bool) -> float:
    scr = creat_umol / 88.4
    k, a = (0.7, -0.241) if female else (0.9, -0.302)
    return 142 * min(scr / k, 1) ** a * max(scr / k, 1) ** -1.200 * 0.9938 ** age * (1.012 if female else 1)


RENAL_BANDS = [(30, None, "30 or above", "1 mg/kg every 12 hours", 1.0, 12),
               (15, 30, "15 to 29", "1 mg/kg once daily", 1.0, 24), (0, 15, "below 15", "do not use; discuss with pharmacist", None, None)]
SYRINGES_MG = [20, 40, 60, 80, 100, 120, 150]  # prefilled enoxaparin syringes: the calculated dose is rounded to the nearest one


def renal_band(egfr: float):
    r = round(egfr)
    for lo, hi, label, text, mgkg, h in RENAL_BANDS:
        if r >= lo:
            return label, text, mgkg, h
    raise ValueError


FERRAND_DATE1, FERRAND_DATE2 = D(2026, 11, 16), D(2026, 11, 17)
FERRAND_CREAT = {FERRAND_DATE1: 175, FERRAND_DATE2: 105}


def ferrand_result(creat: int, on: dt.date):
    p = P["ferrand"]
    e = ckd_epi_2021(creat, p.age_on(on), True)
    label, text, mgkg, h = renal_band(e)
    calc = None if mgkg is None else round(mgkg * p.weight)
    dose = None if calc is None else min(SYRINGES_MG, key=lambda s: (abs(s - calc), s))
    return dict(egfr=round(e), band=label, text=text, calc_mg=calc, dose_mg=dose, every_h=h, raw=e)


# ------------------------------------------------------------------ medicines
HOME_MEDS_MARCHAND = [
    ("Ramipril", "5 mg", "once daily"), ("Bisoprolol", "2.5 mg", "once daily"), ("Atorvastatin", "20 mg", "at night"),
    ("Metformin", "850 mg", "twice daily"), ("Aspirin", "75 mg", "once daily"), ("Omeprazole", "20 mg", "once daily"),
    ("Ibuprofen", "400 mg", "when required")]
DISCHARGE_MEDS_MARCHAND = [
    ("Ramipril", "2.5 mg", "once daily", "CHANGED", "dose reduced from 5 mg: potassium 5.6 mmol/L on 04/11/2026"),
    ("Bisoprolol", "2.5 mg", "once daily", "CONTINUE", ""),
    ("Atorvastatin", "40 mg", "at night", "CHANGED", "dose increased from 20 mg: LDL-cholesterol above target"),
    ("Metformin", "850 mg", "twice daily", "CONTINUE", ""),
    ("Aspirin", "75 mg", "once daily", "CONTINUE", ""),
    ("Omeprazole", "20 mg", "once daily", "CONTINUE", ""),
    ("Ibuprofen", "400 mg", "when required", "STOPPED", "stopped: acute kidney injury, avoid NSAIDs"),
    ("Furosemide", "40 mg", "once daily", "NEW", "fluid overload"),
    ("Apixaban", "5 mg", "twice daily", "NEW", "atrial fibrillation, CHA2DS2-VASc 3")]

# Active drugs of M. Coste on 15/11/2026 and the pharmacy interaction bulletin (pairs: A, B, severity, effect, management)
COSTE_ACTIVE = [("Simvastatin", "40 mg at night"), ("Clarithromycin", "500 mg twice daily (started 13/11/2026, 7 days)"),
                ("Amlodipine", "5 mg once daily"), ("Ramipril", "10 mg once daily"), ("Spironolactone", "25 mg once daily"),
                ("Digoxin", "125 micrograms once daily"), ("Omeprazole", "20 mg once daily"), ("Paracetamol", "1 g up to four times daily")]
INTERACTIONS = [
    ("Simvastatin", "Clarithromycin", "Major", "raised simvastatin exposure: myopathy / rhabdomyolysis",
     "suspend simvastatin for the whole clarithromycin course"),
    ("Digoxin", "Clarithromycin", "Major", "raised digoxin level: toxicity", "avoid; if essential halve the digoxin dose and check the level on day 3"),
    ("Ramipril", "Spironolactone", "Moderate", "hyperkalaemia", "check potassium and creatinine at 1 week"),
    ("Amlodipine", "Simvastatin", "Moderate", "raised simvastatin exposure", "limit simvastatin to 20 mg daily"),
    ("Omeprazole", "Clarithromycin", "Minor", "slightly raised omeprazole level", "no action"),
    ("Digoxin", "Spironolactone", "Minor", "possible small rise in digoxin level", "no action"),
    ("Digoxin", "Omeprazole", "Minor", "small rise in digoxin absorption", "no action"),
    ("Warfarin", "Clarithromycin", "Major", "raised INR, bleeding", "avoid; if essential check INR within 3 days"),
    ("Warfarin", "Amiodarone", "Major", "raised INR, bleeding", "reduce warfarin dose by about a third and check INR weekly"),
    ("Warfarin", "Ciprofloxacin", "Moderate", "raised INR", "check INR within 5 days"),
    ("Methotrexate", "Trimethoprim", "Major", "bone-marrow suppression", "avoid"),
    ("Methotrexate", "Ibuprofen", "Moderate", "reduced methotrexate clearance", "monitor blood count"),
    ("Sildenafil", "Isosorbide mononitrate", "Major", "profound hypotension", "contraindicated"),
    ("Ramipril", "Ibuprofen", "Moderate", "reduced antihypertensive effect, renal impairment", "monitor renal function"),
    ("Lithium", "Ramipril", "Moderate", "raised lithium level", "check lithium level at 1 week"),
    ("Lithium", "Furosemide", "Moderate", "raised lithium level", "check lithium level at 1 week"),
    ("Atorvastatin", "Clarithromycin", "Moderate", "raised atorvastatin exposure", "limit atorvastatin to 20 mg daily"),
    ("Apixaban", "Ketoconazole", "Major", "raised apixaban level: bleeding", "avoid"),
    ("Apixaban", "Aspirin", "Moderate", "additive bleeding risk", "review need for aspirin"),
    ("Clopidogrel", "Omeprazole", "Moderate", "reduced clopidogrel activation", "prefer pantoprazole"),
    ("Sertraline", "Tramadol", "Moderate", "serotonin syndrome, seizures", "use lowest doses, monitor"),
    ("Tramadol", "Ondansetron", "Minor", "reduced analgesic effect", "no action"),
    ("Levothyroxine", "Calcium carbonate", "Minor", "reduced absorption", "separate by 4 hours"),
    ("Furosemide", "Gentamicin", "Moderate", "additive ototoxicity and nephrotoxicity", "monitor renal function"),
    ("Digoxin", "Furosemide", "Moderate", "hypokalaemia raises digoxin toxicity", "check potassium weekly"),
    ("Metformin", "Iodinated contrast", "Moderate", "lactic acidosis if renal function falls", "hold metformin for 48 hours"),
    ("Phenytoin", "Fluconazole", "Major", "raised phenytoin level", "check level, reduce dose"),
    ("Spironolactone", "Trimethoprim", "Moderate", "hyperkalaemia", "check potassium within 1 week"),
    ("Bisoprolol", "Verapamil", "Major", "bradycardia, heart block", "avoid"),
    ("Allopurinol", "Azathioprine", "Major", "bone-marrow suppression", "reduce azathioprine to a quarter of the dose"),
]


def coste_major_pairs():
    names = {n for n, _ in COSTE_ACTIVE}
    return [i for i in INTERACTIONS if i[0] in names and i[1] in names and i[2] == "Major"]


# ------------------------------------------------------------------ warfarin
PERRIN_WEEKLY_MG = 28.0
PERRIN_INR = [(D(2026, 10, 27), 2.4), (D(2026, 11, 3), 2.6), (D(2026, 11, 10), 3.4)]
# nomogram: (low, high, action text, weekly change %, omit doses, recheck days)
NOMOGRAM = [(0.0, 1.49, "increase weekly dose by 15%", +15, 0, 4), (1.5, 1.99, "increase weekly dose by 10%", +10, 0, 7),
            (2.0, 3.0, "no change", 0, 0, 28), (3.01, 3.99, "decrease weekly dose by 10%", -10, 0, 7),
            (4.0, 4.99, "omit one dose, then decrease weekly dose by 15%", -15, 1, 3),
            (5.0, 99.0, "omit two doses, contact the anticoagulation pharmacist, then decrease weekly dose by 20%", -20, 2, 1)]


def nomogram_row(inr: float):
    for row in NOMOGRAM:
        if row[0] <= round(inr, 2) <= row[1]:
            return row
    raise ValueError(inr)


def warfarin_plan(inr: float, on: dt.date, weekly: float = PERRIN_WEEKLY_MG):
    lo, hi, text, pct, omit, days = nomogram_row(inr)
    return dict(text=text, new_weekly=round(weekly * (1 + pct / 100), 1), recheck=on + dt.timedelta(days=days), days=days, omit=omit)


# ------------------------------------------------------------------ vaccination
BLANC_RECORD = [("dTcaP (tetanus-diphtheria-pertussis)", D(2015, 3, 12)), ("Influenza 2025-26", D(2025, 10, 14)),
                ("Zoster recombinant (RZV) dose 1", D(2026, 5, 5)), ("COVID-19 autumn 2026", D(2026, 10, 20))]
VACC_ASOF = D(2026, 11, 20)


def add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]))


def blanc_status():
    rec = dict(BLANC_RECORD)
    tdap_due = add_months(rec["dTcaP (tetanus-diphtheria-pertussis)"], 120)
    rzv_window = (add_months(rec["Zoster recombinant (RZV) dose 1"], 2), add_months(rec["Zoster recombinant (RZV) dose 1"], 6))
    return dict(tdap_due=tdap_due, rzv_window=rzv_window)


# ------------------------------------------------------------------ imaging
ROUSSEL_CT = [(D(2026, 3, 14), 9), (D(2026, 11, 12), 12)]


def nodule_growth_pct():
    a, b = ROUSSEL_CT[0][1], ROUSSEL_CT[1][1]
    return (b - a) / a * 100


def nodule_followup(prev_mm: float, now_mm: float, report: dt.date):
    g = (now_mm - prev_mm) / prev_mm * 100
    if g >= 20:
        return dict(pct=g, action="MDT", due=report + dt.timedelta(days=14))
    return dict(pct=g, action="CT_12M", due=add_months(report, 12))


# ------------------------------------------------------------------ surgical prophylaxis
TESSIER = dict(date=D(2026, 11, 17), abx="Cefazolin", dose_g=2, given="08:21", incision="08:52", weight=124.0)


def minutes_between(a: str, b: str) -> int:
    ha, ma = map(int, a.split(":"))
    hb, mb = map(int, b.split(":"))
    return (hb * 60 + mb) - (ha * 60 + ma)


def prophylaxis_required_dose(weight: float) -> int:
    return 3 if weight >= 120 else 2


# ------------------------------------------------------------------ paediatrics
MOREAU = dict(weight=14.5, prescribed_mg=500, freq_h=6, mg_per_kg=15, day_mg_per_kg=60, conc_mg_per_ml=24.0)


def paed_limits(w=MOREAU["weight"]):
    single = w * MOREAU["mg_per_kg"]
    daily = w * MOREAU["day_mg_per_kg"]
    ml_raw = single / MOREAU["conc_mg_per_ml"]
    return dict(single=single, daily=daily, ml=math.floor(ml_raw * 2) / 2, ml_raw=ml_raw,
                prescribed_daily=MOREAU["prescribed_mg"] * 24 // MOREAU["freq_h"], ratio=MOREAU["prescribed_mg"] / single)


# ------------------------------------------------------------------ MAR: ceftriaxone for Mme Guérin
GUERIN_DOSES = [(D(2026, 11, 3), "G"), (D(2026, 11, 4), "G"), (D(2026, 11, 5), "G"), (D(2026, 11, 6), "N"),
                (D(2026, 11, 7), "G"), (D(2026, 11, 8), "G"), (D(2026, 11, 9), "G")]
GUERIN_N_REASON = "patient off ward for CT scan at scheduled time"
CAP_IV_MAX_DAYS = 3


def guerin_given():
    return [d for d, c in GUERIN_DOSES if c == "G"]


# ------------------------------------------------------------------ Benali pending results
BENALI_DISCHARGE = D(2026, 11, 12)
BENALI_PENDING = [("Blood culture, set 2", "no growth at 5 days", D(2026, 11, 17), False),
                  ("TSH", "9.80 mIU/L (reference 0.40 - 4.00)", D(2026, 11, 13), True),
                  ("25-OH vitamin D", "38 nmol/L (reference 50 - 125)", D(2026, 11, 13), True)]


def gp_deadline(final: dt.date) -> dt.date:
    return add_business_days(final, 2)


# ------------------------------------------------------------------ Martel follow-up
MARTEL_DISCHARGE = D(2026, 11, 6)
MARTEL_REQUIRED = [("Cardiology clinic", 14, "within 14 days"), ("Cardiac rehabilitation assessment", 28, "within 28 days"),
                   ("Transthoracic echocardiogram", 42, "at 6 weeks")]
MARTEL_BOOKED = {"Cardiology clinic": D(2026, 12, 2), "Cardiac rehabilitation assessment": D(2026, 11, 25)}


def martel_status():
    out = []
    for name, days, _ in MARTEL_REQUIRED:
        due = MARTEL_DISCHARGE + dt.timedelta(days=days)
        booked = MARTEL_BOOKED.get(name)
        out.append((name, due, booked, None if booked is None else (booked - due).days))
    return out


# ------------------------------------------------------------------ Ward 4B MRSA screening (14/11/2026)
# bed, patient label, origin, bed type, screen
WARD4B = [("4B-01", "Aubert, C.", "Home", "Bay", "Negative"), ("4B-02", "Bernier, T.", "Care home", "Bay", "Positive"),
          ("4B-03", "Carpentier, M.", "Home", "Bay", "Negative"), ("4B-04", "Delmas, R.", "Transfer from another hospital", "Bay", "Pending"),
          ("4B-05", "Escoffier, P.", "Home", "Bay", "Pending"), ("4B-06", "Fournier, J.", "Care home", "Single room", "Positive"),
          ("4B-07", "Gaillard, S.", "Home", "Bay", "Positive"), ("4B-08", "Hamon, L.", "Home", "Bay", "Negative"),
          ("4B-09", "Imbert, A.", "Transfer from another hospital", "Single room", "Pending"),
          ("4B-10", "Joly, N.", "Home", "Bay", "Negative"), ("4B-11", "Klein, F.", "Care home", "Bay", "Negative"),
          ("4B-12", "Laurent, V.", "Transfer from another hospital", "Bay", "Negative")]


def ward4b_needing_isolation_in_bay():
    return [r for r in WARD4B if r[3] == "Bay" and (r[4] == "Positive" or (r[4] == "Pending" and r[2].startswith("Transfer")))]


# ------------------------------------------------------------------ NEWS2 (Fabre)
def news2(rr, spo2, on_o2, sbp, hr, alert, temp):
    s = 0
    s += 3 if rr <= 8 else 1 if rr <= 11 else 0 if rr <= 20 else 2 if rr <= 24 else 3
    s += 3 if spo2 <= 91 else 2 if spo2 <= 93 else 1 if spo2 <= 95 else 0
    s += 2 if on_o2 else 0
    s += 3 if sbp <= 90 else 2 if sbp <= 100 else 1 if sbp <= 110 else 0 if sbp <= 219 else 3
    s += 3 if hr <= 40 else 1 if hr <= 50 else 0 if hr <= 90 else 1 if hr <= 110 else 2 if hr <= 130 else 3
    s += 0 if alert else 3
    s += 3 if temp <= 35.0 else 1 if temp <= 36.0 else 0 if temp <= 38.0 else 1 if temp <= 39.0 else 2
    return s


FABRE_OBS = [("00:00", 18, 96, False, 128, 84, True, 37.2), ("03:00", 20, 94, False, 118, 92, True, 37.8),
             ("06:00", 22, 95, True, 108, 94, True, 37.8), ("09:00", 24, 93, True, 104, 104, True, 38.4),
             ("12:00", 20, 96, True, 112, 88, True, 37.6)]
FABRE_DATE = D(2026, 11, 15)


def fabre_scores():
    return [(t, news2(rr, sp, o2, sbp, hr, al, tp)) for t, rr, sp, o2, sbp, hr, al, tp in FABRE_OBS]


def news2_response(score: int, single3: bool = False) -> str:
    if score >= 7:
        return "emergency response: continuous monitoring and immediate assessment by the critical care outreach team"
    if score >= 5:
        return "urgent response: urgent review by a clinician within 30 minutes, observations at least hourly"
    if single3:
        return "urgent ward-based response"
    if score >= 1:
        return "ward-based response: nurse decides on observation frequency, at least every 4-6 hours"
    return "routine monitoring: observations at least every 12 hours"


# ------------------------------------------------------------------ Insulin sliding scale (Renard, 10/11/2026)
INSULIN_SCALE = [(0, 3.9, 0, "hypoglycaemia protocol"), (4.0, 7.9, 0, ""), (8.0, 11.9, 2, ""), (12.0, 15.9, 4, ""),
                 (16.0, 19.9, 6, ""), (20.0, 999, 8, "and call the doctor")]
RENARD = [("07:30", 12.4, 4), ("12:00", 8.1, 2), ("17:30", 15.6, 6), ("21:30", 6.2, 0)]  # time, glucose, units given


def scale_units(g: float) -> int:
    for lo, hi, u, _ in INSULIN_SCALE:
        if lo <= g <= hi + 0.0999:
            return u
    raise ValueError(g)


# ------------------------------------------------------------------ Formulary / Caron
CARON_CHART = [("Apixaban", "5 mg twice daily"), ("Pantoprazole", "40 mg once daily"), ("Pregabalin", "75 mg twice daily"),
               ("Tolvaptan", "15 mg once daily"), ("Sacubitril/valsartan", "49/51 mg twice daily"),
               ("Furosemide", "40 mg once daily"), ("Linaclotide", "290 micrograms once daily"),
               ("Paracetamol", "1 g up to four times daily"), ("Bisoprolol", "2.5 mg once daily")]
FORMULARY_STATUS = {  # F formulary, R restricted (named specialty approval), NF non-formulary (D&T approval per patient)
    "Apixaban": ("F", ""), "Pantoprazole": ("F", ""), "Pregabalin": ("F", ""), "Furosemide": ("F", ""), "Paracetamol": ("F", ""),
    "Bisoprolol": ("F", ""), "Sacubitril/valsartan": ("R", "cardiology consultant initiation"), "Linaclotide": ("R", "gastroenterology consultant initiation"),
    "Tolvaptan": ("NF", "individual patient approval by the Drug and Therapeutics Committee (D&T)"),
    "Rivaroxaban": ("NF", "individual patient approval by D&T"), "Ramipril": ("F", ""), "Atorvastatin": ("F", ""),
    "Metformin": ("F", ""), "Amlodipine": ("F", ""), "Omeprazole": ("F", ""), "Aspirin": ("F", ""), "Spironolactone": ("F", ""),
    "Digoxin": ("F", ""), "Simvastatin": ("F", ""), "Clarithromycin": ("F", ""), "Amoxicillin": ("F", ""), "Doxycycline": ("F", ""),
    "Ceftriaxone": ("F", ""), "Enoxaparin": ("F", ""), "Warfarin": ("F", ""), "Insulin aspart": ("F", ""),
    "Cefazolin": ("F", ""), "Ibuprofen": ("F", ""), "Ticagrelor": ("R", "cardiology consultant initiation"),
    "Dapagliflozin": ("R", "cardiology or diabetology consultant initiation"), "Denosumab": ("NF", "individual patient approval by D&T"),
    "Lansoprazole": ("NF", "pantoprazole is the formulary PPI alternative"), "Ondansetron": ("F", ""), "Tramadol": ("F", ""),
    "Sertraline": ("F", ""), "Levothyroxine": ("F", ""), "Allopurinol": ("F", ""), "Gentamicin": ("F", ""),
    "Pregabalin XR": ("NF", "use standard-release pregabalin"), "Eplerenone": ("R", "cardiology consultant initiation"),
}
CARON_APPROVAL = dict(drug="Tolvaptan", approver="Dr Élise Maurel, Chair of the Drug and Therapeutics Committee",
                      start=D(2026, 11, 16), days=14)
CARON_ASOF = D(2026, 11, 18)


def caron_flagged():
    return [(n, d, FORMULARY_STATUS[n][0]) for n, d in CARON_CHART if FORMULARY_STATUS[n][0] != "F"]


if __name__ == "__main__":
    for dte, c in FERRAND_CREAT.items():
        print(dte, ferrand_result(c, dte))
    print(blanc_status(), nodule_growth_pct(), nodule_followup(9, 12, D(2026, 11, 12)), nodule_followup(9, 10, D(2026, 11, 12)))
    print(paed_limits(), fabre_scores(), [scale_units(g) for _, g, _ in RENARD])
    print(warfarin_plan(3.4, D(2026, 11, 10)), warfarin_plan(4.3, D(2026, 11, 10)))
    print(martel_status(), [gp_deadline(f) for _, _, f, a in BENALI_PENDING], coste_major_pairs()[:2], caron_flagged())
    print([r[0] for r in ward4b_needing_isolation_in_bay()], abnormal(P['delaunay'], LAB_DELAUNAY[D(2026, 11, 12)]))
