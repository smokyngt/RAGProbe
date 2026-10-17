"""CareBench questions 22-34 (13 conversations, 39 rows): rules applied to patients already in the corpus, protocol lookups
asked as hypothetical cases, and aggregations over tables. Called from build_dataset.py; expected values come from scenario.py
and from the same row generators that print the documents."""
from __future__ import annotations

import collections
import datetime as dt

import scenario as S
from scenario import D, fd


def build_more(B):
    ev, kf, calc, main_q, follow_up = B.ev, B.kf, B.calc, B.main_q, B.follow_up
    import corpus as C  # same row generators as the documents

    REN = "PHA-REN-02_Renal_Dose_Adjustment_Protocol_v4"
    L05, L12 = "LAB_Delaunay_Marc_2026-11-05", "LAB_Delaunay_Marc_2026-11-12"
    dl = S.P["delaunay"]
    male = "142 * ((creat_umol / 88.4) / 0.9) ** -1.2 * 0.9938 ** age"
    e = lambda c, age, fem=False: S.ckd_epi_2021(c, age, fem)
    e05, e12, e140 = round(e(121, 71)), round(e(128, 71)), round(e(140, 71))
    assert (e05, e12) == (55, 52) and e140 < 50

    # ---- 22. eGFR trend, male (Delaunay)
    q = main_q(22,
        "Using protocol PHA-REN-02, calculate Marc Delaunay's (MRN 4471823) eGFR from the serum creatinine of each of his two laboratory reports (05/11/2026 and 12/11/2026), rounded to the nearest whole number, and say how it changed.",
        "What's Mr Delaunay's kidney function on his two latest blood tests, and is it getting worse?",
        f"05/11/2026: creatinine 121 µmol/L gives an eGFR of {e05} mL/min/1.73 m2. 12/11/2026: creatinine 128 µmol/L gives {e12}. The eGFR fell by 3 mL/min/1.73 m2 (from 55 to 52); he is a 71-year-old man (kappa 0.9, alpha -0.302).",
        [kf("eGFR 05/11", "55"), kf("eGFR 12/11", "52"), kf("direction", "fell", "decreased", "lower", "worse")],
        [ev(L05, "Age 71 years … Creatinine 121 µmol/L"), ev(L12, "Age 71 years … Creatinine 128 µmol/L"), ev(REN, "Male kappa = 0.9, alpha = -0.302"),
         ev(REN, "eGFR = 142 x min(Scr/kappa, 1)^alpha x max(Scr/kappa, 1)^-1.200 x 0.9938^Age x 1.012 [if female]")],
        type="calculation", difficulty="hard", style="trend", domain="pharmacy", rule="CKD-EPI 2021 eGFR, male, two dates", safety=True,
        fmt="two eGFR values | change", modes=["same_analyte_multiple_dates", "unit_conversion", "multi_document_join", "derived_value"],
        skills=["unit_conversion", "formula_evaluation"],
        calculation=calc({"creat_umol": 128, "age": 71}, male, e(128, 71), {"creat_umol": (1, "128", "µmol/L", 1), "age": (1, "71", "years", 1)}))
    follow_up(q, "next_step", "Under protocol PHA-REN-02, does Marc Delaunay's eGFR of 12/11/2026 call for extended-interval, level-guided gentamicin dosing?",
        "Would that call for the special gentamicin dosing?",
        f"No. The protocol requires extended-interval, level-guided gentamicin dosing when the eGFR is below 50; his eGFR on 12/11/2026 is {e12}, which is not below 50.",
        [kf("answer", "No"), kf("threshold", "below 50"), kf("his eGFR", "52")],
        [ev(REN, "Gentamicin below 50 extended interval, level-guided"), ev(L12, "Age 71 years … Creatinine 128 µmol/L")],
        type="multi_document", difficulty="medium", style="yes_no", domain="pharmacy", rule="Gentamicin rule below eGFR 50", fmt="yes/no with figures",
        modes=["multi_document_join", "threshold_boundary", "table_in_protocol"], skills=["threshold_comparison"], safety=True)
    follow_up(q, "hypothetical_variation", "If Marc Delaunay's creatinine on 12/11/2026 had been 140 µmol/L instead (age unchanged), what would his eGFR be and would the gentamicin rule then apply?",
        "And if his creatinine had been 140?",
        f"Creatinine 140 µmol/L gives an eGFR of {e140} mL/min/1.73 m2, below 50, so extended-interval, level-guided gentamicin dosing would apply.",
        [kf("eGFR", str(e140)), kf("threshold", "below 50"), kf("rule", "extended-interval", "extended interval")],
        [ev(L12, "Age 71 years … Creatinine 128 µmol/L"), ev(REN, "Gentamicin below 50 extended interval, level-guided"), ev(REN, "Male kappa = 0.9, alpha = -0.302")],
        type="multi_evidence", difficulty="hard", style="conditional", domain="pharmacy", rule="CKD-EPI 2021 eGFR, male, hypothetical creatinine", safety=True, fmt="eGFR | yes/no",
        modes=["hypothetical_variation", "unit_conversion", "threshold_boundary"], skills=["unit_conversion", "formula_evaluation", "threshold_comparison"])

    # ---- 23. metformin and eGFR (Giraud)
    GL, GA = "LAB_Girard_Henri_2026-11-16", "ADM_Giraud_Henri_2026-11-13"
    g = S.P["giraud"]
    eg, eg150 = round(e(214, 69)), round(e(150, 69))
    assert eg == 28 and 30 <= eg150 <= 44
    q = main_q(23,
        "Using the creatinine of the 16/11/2026 laboratory report headed GIRAUD Henri (MRN 5502414) and protocol PHA-REN-02, what is his eGFR and what does the protocol say about metformin? Give his home metformin dose from his admission note.",
        "Mr Giraud is on metformin: is that still OK with his kidney function on the 16th?",
        f"Creatinine 214 µmol/L in a 69-year-old man gives an eGFR of {eg} mL/min/1.73 m2, below 30: the protocol says to stop metformin. His home dose is 1,000 mg twice daily (2,000 mg per day).",
        [kf("eGFR", "28"), kf("protocol action", "stop"), kf("home dose", "1,000 mg twice daily", "1 g twice daily", "1,000 mg", "1 g")],
        [ev(GL, "Age 69 years … Creatinine 214 µmol/L"), ev(REN, "Metformin below 30 stop"), ev(GA, "Metformin 1,000 mg twice daily")],
        type="calculation", difficulty="hard", style="conditional", domain="medication_safety", rule="Metformin by eGFR band", safety=True, fmt="eGFR | protocol action | home dose",
        modes=["similar_patient_names", "multi_document_join", "unit_conversion", "derived_value"], skills=["unit_conversion", "formula_evaluation", "table_lookup"],
        calculation=calc({"creat_umol": 214, "age": 69}, male, e(214, 69), {"creat_umol": (0, "214", "µmol/L", 1), "age": (0, "69", "years", 1)}))
    follow_up(q, "next_step", "Does Henri Giraud's (MRN 5502414) admission plan of 13/11/2026 already address his metformin?", "Is the metformin already dealt with in his plan?",
        "Yes: the admission plan includes \"Stop metformin\".",
        [kf("answer", "Yes"), kf("plan item", "Stop metformin")], [ev(GA, "Stop metformin")],
        type="direct", difficulty="easy", style="yes_no", domain="medication_safety", rule="Plan consistent with the renal rule", fmt="yes/no", modes=["similar_patient_names"], skills=["extraction"], safety=True)
    follow_up(q, "hypothetical_variation", "If Henri Giraud's creatinine had been 150 µmol/L instead (age 69), what would his eGFR be and what would protocol PHA-REN-02 allow for metformin? Is his home dose above that?",
        "And if his creatinine had been 150?",
        f"Creatinine 150 µmol/L gives an eGFR of {eg150} mL/min/1.73 m2, in the 30 to 44 band: maximum 1,000 mg of metformin per day. His home dose of 2,000 mg per day (1,000 mg twice daily) is 1,000 mg above that maximum.",
        [kf("eGFR", str(eg150)), kf("maximum", "1,000 mg", "1,000 mg per day", "1000 mg"), kf("home dose above", "2,000 mg per day", "2 g per day", "2,000 mg")],
        [ev(REN, "Metformin 30 to 44 maximum 1,000 mg per day"), ev(GA, "Metformin 1,000 mg twice daily")],
        type="multi_document", difficulty="hard", style="conditional", domain="medication_safety", rule="Metformin by eGFR band", safety=True, fmt="eGFR | maximum | exceeds?",
        modes=["hypothetical_variation", "unit_conversion", "table_in_protocol"], skills=["formula_evaluation", "table_lookup", "threshold_comparison"])
    B.ROWS[-1]["metadata"]["requires_calculation"] = False

    # ---- 24. paediatric ibuprofen and amoxicillin (Moreau)
    PM, PH = "PRESC_Moreau_Lea_2026-11-16", "PAE-DOS-01_Paediatric_Dosing_Handbook_2026"
    w = 14.5
    q = main_q(24,
        "Check Léa Moreau's (MRN 4492206) ibuprofen prescription of 16/11/2026 against the Paediatric Dosing Handbook. Give the acceptable single-dose range in mg and the maximum daily dose in mg for her measured weight, the maximum daily amount the prescription can deliver, and say whether it is within the limits.",
        "Is the ibuprofen prescribed for Léa Moreau within limits?",
        "At 14.5 kg the single dose may be 5 to 10 mg/kg, i.e. 72.5 to 145 mg, and the maximum daily dose is 30 mg/kg = 435 mg. The prescription is 100 mg every 8 hours as required: at most 3 doses = 300 mg per day, i.e. 6.9 mg/kg per dose. It is within all the limits.",
        [kf("single-dose range low", "72.5"), kf("single-dose range high", "145"), kf("max daily", "435 mg"), kf("prescribed daily", "300 mg"), kf("verdict", "within")],
        [ev(PM, "Poids mesuré 14,5 kg"), ev(PM, "Ibuprofène suspension buvable 100 mg PO toutes les 8 heures si douleur"), ev(PH, "Single dose 5 to 10 mg/kg per dose"),
         ev(PH, "Maximum daily dose 30 mg/kg per 24 hours")],
        type="calculation", difficulty="medium", style="yes_no", domain="pharmacy", rule="Paediatric weight-based ibuprofen limits", safety=True, fmt="range | max daily | prescribed | verdict",
        modes=["french_document", "multi_document_join", "derived_value"], skills=["unit_arithmetic", "threshold_comparison"],
        calculation=calc({"weight_kg": w, "mg_per_kg_day": 30}, "weight_kg * mg_per_kg_day", 435.0, {"weight_kg": (0, "14,5", "kg", 1), "mg_per_kg_day": (3, "30", "mg/kg", 1)}))
    follow_up(q, "scope_change", "What dose of amoxicillin per administration does the Paediatric Dosing Handbook give for Léa Moreau's weight, and does the per-dose maximum apply?", "And if she needed amoxicillin, what dose would that be?",
        "The standard dose is 25 mg/kg three times daily: 14.5 kg x 25 = 362.5 mg per dose. The maximum is 1 g per dose, which is not reached.",
        [kf("dose", "362.5 mg"), kf("rule", "25 mg/kg"), kf("maximum", "1 g")],
        [ev(PM, "Poids mesuré 14,5 kg"), ev(PH, "Standard dose 25 mg/kg three times daily"), ev(PH, "Maximum 1 g per dose")],
        type="calculation", difficulty="medium", style="conditional", domain="pharmacy", rule="Paediatric weight-based amoxicillin dose", safety=True, fmt="dose in mg",
        modes=["french_document", "hypothetical_variation", "derived_value"], skills=["unit_arithmetic"],
        calculation=calc({"weight_kg": w, "mg_per_kg": 25}, "weight_kg * mg_per_kg", 362.5, {"weight_kg": (0, "14,5", "kg", 1), "mg_per_kg": (1, "25", "mg/kg", 1)}))
    follow_up(q, "drill_down", "Is the 8-hour interval of Léa Moreau's ibuprofen prescription consistent with the handbook's interval for ibuprofen?", "Is the dosing interval OK?",
        "Yes. The handbook gives every 6 to 8 hours for ibuprofen; every 8 hours is within the interval (at its upper end).",
        [kf("answer", "Yes"), kf("handbook interval", "6 to 8 hours")], [ev(PM, "Ibuprofène suspension buvable 100 mg PO toutes les 8 heures si douleur"), ev(PH, "Interval every 6 to 8 hours")],
        type="multi_document", difficulty="easy", style="yes_no", domain="pharmacy", rule="Ibuprofen interval", fmt="yes/no", modes=["french_document", "multi_document_join"], skills=["threshold_comparison"], safety=True)

    # ---- 25. largest relative changes (Delaunay)
    p05, p12 = S.LAB_DELAUNAY[D(2026, 11, 5)], S.LAB_DELAUNAY[D(2026, 11, 12)]
    ch = sorted(((abs(p12[k] - p05[k]) / p05[k] * 100, k) for k in p05 if p05[k]), reverse=True)
    assert [k for _, k in ch[:3]] == ["CRP", "ALT", "Urea"] and ch[3][1] == "WBC"
    q = main_q(25,
        "Between Marc Delaunay's laboratory reports of 05/11/2026 and 12/11/2026, which three analytes show the largest relative change (in absolute value, as a percentage of the 05/11/2026 result)? Give each analyte, both results and the percentage change.",
        "Which blood results moved the most for Mr Delaunay in the last week?",
        "The three largest relative changes are: C-reactive protein, from 96 to 38 mg/L (-60.4%); ALT, from 38 to 52 U/L (+36.8%); urea, from 8.4 to 9.6 mmol/L (+14.3%). White cell count comes next (13.5 to 11.8, -12.6%).",
        [kf("CRP change", "60.4%", "60%"), kf("ALT change", "36.8%", "37%"), kf("urea change", "14.3%", "14%"), kf("ALT results", "38"), kf("urea results", "8.4")],
        [ev(L05, "C-reactive protein 96 mg/L 0-5 H"), ev(L12, "C-reactive protein 38 mg/L 0-5 H"), ev(L05, "ALT 38 U/L 7 - 40"), ev(L12, "ALT 52 U/L 7 - 40 H"),
         ev(L05, "Urea 8.4 mmol/L 2.5 - 7.8 H"), ev(L12, "Urea 9.6 mmol/L 2.5 - 7.8 H"), ev(L05, "White cell count 13.5 10^9/L 4.0 - 10.0 H"), ev(L12, "White cell count 11.8 10^9/L 4.0 - 10.0 H")],
        type="multi_evidence", difficulty="hard", style="ranking", domain="laboratory", rule="Rank analytes by relative change between two reports", fmt="top three with values and percentages",
        modes=["same_analyte_multiple_dates", "multi_document_join", "derived_value"], skills=["percentage_change", "ranking"])
    follow_up(q, "calculation", "By what percentage did Marc Delaunay's platelet count change between the reports of 05/11/2026 and 12/11/2026?", "And his platelets?",
        "Platelets rose from 150 to 164 x10^9/L: +9.3% of the 05/11/2026 value (+14 x10^9/L); both values are within range.",
        [kf("change", "9.3%", "9%", "9.33%"), kf("before", "150"), kf("after", "164")],
        [ev(L05, "Platelets 150 10^9/L 150 - 400"), ev(L12, "Platelets 164 10^9/L 150 - 400")],
        type="calculation", difficulty="easy", style="trend", domain="laboratory", rule="Percentage change between two results", fmt="percentage",
        modes=["same_analyte_multiple_dates", "threshold_boundary", "multi_document_join"], skills=["percentage_change"],
        calculation=calc({"before": 150, "after": 164}, "(after - before) / before * 100", 14 / 150 * 100, {"before": (0, "150", "10^9/L", 1), "after": (1, "164", "10^9/L", 1)}))
    follow_up(q, "comparison" if False else "compare_over_time", "Which changed more in relative terms between 05/11/2026 and 12/11/2026 for Marc Delaunay: haemoglobin or white cell count?", "Which moved more, his haemoglobin or his white count?",
        "The white cell count: 13.5 to 11.8 x10^9/L, -12.6%, against haemoglobin 122 to 118 g/L, -3.3%.",
        [kf("answer", "white cell count"), kf("WBC change", "12.6%", "13%"), kf("Hb change", "3.3%", "3%")],
        [ev(L05, "White cell count 13.5 10^9/L 4.0 - 10.0 H"), ev(L12, "White cell count 11.8 10^9/L 4.0 - 10.0 H"), ev(L05, "Haemoglobin 122 g/L 130 - 175 L"), ev(L12, "Haemoglobin 118 g/L 130 - 175 L")],
        type="multi_evidence", difficulty="medium", style="comparison", domain="laboratory", rule="Compare two relative changes", fmt="answer with both percentages",
        modes=["same_analyte_multiple_dates", "multi_document_join", "derived_value"], skills=["percentage_change", "comparison"])

    # ---- 26. Ward 4B counts
    W4 = "IPC_MRSA_screening_Ward4B_2026-11-14"
    wrow = lambda r: f"{r[0]} {r[1]} {r[2]} {r[3]} {r[4]}"
    single = [r for r in S.WARD4B if r[3] == "Single room"]
    cnt = collections.Counter(r[4] for r in S.WARD4B)
    pend_tr = [r for r in S.WARD4B if r[4] == "Pending" and r[2].startswith("Transfer")]
    assert [r[0] for r in single] == ["4B-06", "4B-09"] and (cnt["Positive"], cnt["Negative"], cnt["Pending"]) == (3, 6, 3) and [r[0] for r in pend_tr] == ["4B-04", "4B-09"]
    q = main_q(26,
        "On Ward 4B, in the MRSA screening list at 14/11/2026, how many patients are in a single room? Give bed and patient.",
        "How many Ward 4B patients are in single rooms on the 14th?",
        "Two: bed 4B-06 (Fournier, J.) and bed 4B-09 (Imbert, A.). The other ten patients are in bays.",
        [kf("count", "Two", "2"), kf("bed", "4B-06"), kf("bed", "4B-09")],
        [ev(W4, wrow(single[0])), ev(W4, wrow(single[1]))],
        type="table", difficulty="easy", style="count", domain="infection_control", rule="Count rows of a table", fmt="count | beds", modes=["decoy_similar_rows"], skills=["counting", "filtering"])
    follow_up(q, "aggregate", "On Ward 4B at 14/11/2026, how many patients have an MRSA screen result of positive, negative and pending?", "And how many are positive, negative, pending?",
        "Positive: 3 (4B-02, 4B-06, 4B-07). Negative: 6 (4B-01, 4B-03, 4B-08, 4B-10, 4B-11, 4B-12). Pending: 3 (4B-04, 4B-05, 4B-09). Total 12.",
        [kf("positive", "3"), kf("negative", "6"), kf("pending", "3"), kf("total", "12")], [ev(W4, wrow(r)) for r in S.WARD4B],
        type="table", difficulty="medium", style="count", domain="infection_control", rule="Group and count rows of a table", fmt="three counts", modes=["decoy_similar_rows"], skills=["counting", "grouping"])
    follow_up(q, "drill_down", "How many of the pending MRSA screens on Ward 4B at 14/11/2026 are for patients transferred from another hospital, and are those patients isolated?", "Of the pending ones, how many came from another hospital, and are they isolated?",
        "Two: 4B-04 (Delmas, R.), who is in a bay and therefore not isolated, and 4B-09 (Imbert, A.), who is in a single room. The third pending patient (4B-05) comes from home.",
        [kf("count", "Two", "2"), kf("not isolated", "4B-04"), kf("isolated", "4B-09")], [ev(W4, wrow(r)) for r in S.WARD4B if r[4] == "Pending"],
        type="table", difficulty="medium", style="count", domain="infection_control", rule="Filter rows on two columns", fmt="count | isolation status", modes=["decoy_similar_rows"], skills=["filtering", "counting"])

    # ---- 27. clinic bookings export
    BK = "Clinic_Bookings_Export_2026-11-19"
    rows = C.booking_rows()
    dd = lambda r: dt.datetime.strptime(r[3], "%d/%m/%Y").date()
    brow = lambda r: f"{r[0]} {r[1]} {r[2]} {r[3]} {r[4]}"
    card = [r for r in rows if r[2] == "Cardiology clinic" and dd(r) <= D(2026, 11, 30)]
    assert [r[3] for r in card] == ["27/11/2026", "30/11/2026"]
    byday = collections.Counter(r[3] for r in rows)
    top_day, top_n = byday.most_common(1)[0]
    assert top_day == "28/12/2026" and top_n == 7 and byday.most_common(2)[1][1] < 7
    diab = [r for r in rows if r[2] == "Diabetes clinic"]
    assert len(diab) == 10
    q = main_q(27,
        "In the outpatient clinic bookings export of 19/11/2026, how many Cardiology clinic bookings fall between 20/11/2026 and 30/11/2026 inclusive? Give the patient, date and time of each.",
        "How many cardiology clinic bookings are there before the end of November?",
        f"Two: {card[0][0]} on {card[0][3]} at {card[0][4]} and {card[1][0]} on {card[1][3]} at {card[1][4]}. Jacques Martel's cardiology clinic is booked on 02/12/2026, outside the window.",
        [kf("count", "Two", "2"), kf("first booking", card[0][0]), kf("second booking", card[1][0])], [ev(BK, brow(r)) for r in card],
        type="table", difficulty="hard", style="count", domain="care_transition", rule="Filter a long table by clinic and date window", fmt="count | patient, date, time",
        modes=["deep_in_report", "decoy_similar_rows", "split_across_pages"], skills=["filtering", "counting", "date_comparison"])
    follow_up(q, "aggregate", "In the bookings export of 19/11/2026, which single day has the most bookings (all clinics) and how many?", "Which day is the busiest in the whole export?",
        f"{top_day} has the most bookings: {top_n}.",
        [kf("day", top_day), kf("count", "7", "seven")], [ev(BK, brow(r)) for r in rows if r[3] == top_day],
        type="table", difficulty="hard", style="superlative", domain="care_transition", rule="Group a long table by date", fmt="date | count", modes=["deep_in_report", "split_across_pages"], skills=["grouping", "counting"])
    follow_up(q, "aggregate", "How many Diabetes clinic bookings does the export of 19/11/2026 contain in total?", "And how many diabetes clinic bookings in total?",
        "Ten Diabetes clinic bookings.", [kf("count", "Ten", "10")], [ev(BK, brow(r)) for r in diab],
        type="table", difficulty="hard", style="count", domain="care_transition", rule="Count rows of a long table by clinic", fmt="count", modes=["deep_in_report", "split_across_pages"], skills=["filtering", "counting"])

    # ---- 28. formulary lookups
    FOR = "PHA-FOR-00_Hospital_Formulary_2026-2027"
    frow = lambda n: f"{n} {S.FORMULARY_STATUS[n][0]} {S.FORMULARY_STATUS[n][1]}".strip()
    nf = sorted(n for n, (st, _) in S.FORMULARY_STATUS.items() if st == "NF")
    assert nf == ["Denosumab", "Lansoprazole", "Pregabalin XR", "Rivaroxaban", "Tolvaptan"]
    q = main_q(28,
        "How many medicines are listed as non-formulary (NF) in the 2026-2027 hospital formulary, and which are they?",
        "Which drugs in the formulary are non-formulary?",
        "Five: denosumab, lansoprazole, pregabalin XR, rivaroxaban and tolvaptan.",
        [kf("count", "Five", "5"), kf("drug", "denosumab"), kf("drug", "lansoprazole"), kf("drug", "pregabalin XR"), kf("drug", "rivaroxaban"), kf("drug", "tolvaptan")],
        [ev(FOR, frow(n)) for n in nf],
        type="table", difficulty="medium", style="list", domain="medication_safety", rule="Filter the formulary on status NF", fmt="count | list", modes=["table_in_protocol", "deep_in_report"], skills=["filtering", "counting"])
    follow_up(q, "drill_down", "For which of the non-formulary medicines does the formulary name a formulary alternative?", "Does it suggest alternatives for any of them?",
        "Two: lansoprazole (pantoprazole is the formulary PPI alternative) and pregabalin XR (use standard-release pregabalin).",
        [kf("drug 1", "lansoprazole"), kf("alternative 1", "pantoprazole"), kf("drug 2", "pregabalin XR"), kf("alternative 2", "standard-release pregabalin")],
        [ev(FOR, frow("Lansoprazole")), ev(FOR, frow("Pregabalin XR"))],
        type="multi_evidence", difficulty="medium", style="list", domain="medication_safety", rule="Alternatives to non-formulary drugs", fmt="drug | alternative", modes=["table_in_protocol"], skills=["extraction"])
    follow_up(q, "scope_change", "Which medicines in the formulary are restricted (R) with initiation by a cardiology consultant? Mention if another specialty is also allowed.", "And the restricted ones that cardiology starts?",
        "Four restricted medicines allow cardiology consultant initiation: eplerenone, sacubitril/valsartan, ticagrelor and dapagliflozin (cardiology or diabetology consultant).",
        [kf("drug", "eplerenone"), kf("drug", "sacubitril/valsartan"), kf("drug", "ticagrelor"), kf("drug", "dapagliflozin"), kf("other specialty", "diabetology")],
        [ev(FOR, frow(n)) for n in ("Eplerenone", "Sacubitril/valsartan", "Ticagrelor", "Dapagliflozin")],
        type="multi_evidence", difficulty="medium", style="list", domain="medication_safety", rule="Filter restricted drugs by specialty", fmt="list", modes=["table_in_protocol", "deep_in_report"], skills=["filtering"])

    # ---- 29. UTI regimens (protocol lookups as a conversation)
    ANTI = "PHA-ANT-01_Antibiotic_Prescribing_Policy_v7"
    q = main_q(29,
        "According to antibiotic policy PHA-ANT-01, what is the first-line regimen and duration for a lower urinary tract infection in a man?",
        "What do we give a man with a simple lower UTI, and for how long?",
        "Trimethoprim 200 mg twice daily for 7 days.",
        [kf("drug", "trimethoprim"), kf("dose", "200 mg twice daily"), kf("duration", "7 days")], [ev(ANTI, "Lower, male Trimethoprim 200 mg twice daily 7 days")],
        type="direct", difficulty="easy", style="lookup", domain="antimicrobial_stewardship", rule="UTI first-line regimens", fmt="regimen | duration", modes=["table_in_protocol"], skills=["table_lookup"])
    follow_up(q, "scope_change", "According to antibiotic policy PHA-ANT-01, what is the first-line regimen and duration for a lower urinary tract infection in a woman?", "And for a woman?",
        "Nitrofurantoin 100 mg modified-release twice daily for 3 days.",
        [kf("drug", "nitrofurantoin"), kf("dose", "100 mg modified-release twice daily", "100 mg"), kf("duration", "3 days")], [ev(ANTI, "Lower, female Nitrofurantoin 100 mg modified-release twice daily 3 days")],
        type="direct", difficulty="easy", style="lookup", domain="antimicrobial_stewardship", rule="UTI first-line regimens", fmt="regimen | duration", modes=["table_in_protocol"], skills=["table_lookup"])
    follow_up(q, "scope_change", "According to antibiotic policy PHA-ANT-01, what is the first-line regimen, route and duration for pyelonephritis?", "What if it's pyelonephritis?",
        "Co-amoxiclav 1.2 g three times daily intravenously, then oral, for 7 days.",
        [kf("drug", "co-amoxiclav"), kf("dose", "1.2 g three times daily", "1.2 g"), kf("duration", "7 days")], [ev(ANTI, "Pyelonephritis Co-amoxiclav 1.2 g three times daily IV, then oral 7 days")],
        type="direct", difficulty="easy", style="lookup", domain="antimicrobial_stewardship", rule="UTI first-line regimens", fmt="regimen | duration", modes=["table_in_protocol"], skills=["table_lookup"])

    # ---- 30. C. difficile precautions (French manual)
    IPC = "IPC-MAN-01_Manuel_de_prevention_des_infections_v6"
    q = main_q(30,
        "What isolation and hand-hygiene measures does infection prevention manual IPC-MAN-01 require for Clostridioides difficile, and until when do the contact precautions last?",
        "What precautions do we need for C. diff, and for how long?",
        "A single room with its own toilet facilities; hand washing with soap and water (alcohol-based hand rub is not sufficient); contact precautions until 48 hours after the stools have returned to normal.",
        [kf("room", "single room", "chambre individuelle"), kf("hand hygiene", "soap and water", "eau et au savon"), kf("end of precautions", "48 hours", "48 heures")],
        [ev(IPC, "Chambre individuelle avec sanitaires dédiés, lavage des mains à l'eau et au savon … précautions contact jusqu'à 48 heures après la normalisation des selles.")],
        type="direct", difficulty="medium", style="list", domain="infection_control", rule="C. difficile precautions", fmt="room | hand hygiene | duration", modes=["french_document"], skills=["extraction"], safety=True)
    follow_up(q, "hypothetical_variation", "A patient with C. difficile has normal stools from 16/11/2026 at 08:00. When can contact precautions end according to manual IPC-MAN-01?", "If his stools were back to normal on the 16th at 8 am, when can we stop?",
        "48 hours after normalisation: not before 18/11/2026 at 08:00.",
        [kf("date", "18/11/2026"), kf("time", "08:00"), kf("delay", "48 hours")], [ev(IPC, "Chambre individuelle avec sanitaires dédiés, lavage des mains à l'eau et au savon … précautions contact jusqu'à 48 heures après la normalisation des selles.")],
        type="temporal", difficulty="medium", style="conditional", domain="infection_control", rule="C. difficile precautions end", fmt="date and time", modes=["french_document", "hypothetical_variation", "derived_value"], skills=["date_arithmetic"])
    follow_up(q, "drill_down", "Can alcohol-based hand rub replace hand washing when caring for a patient with C. difficile, according to manual IPC-MAN-01?", "Can we just use the alcohol gel?",
        "No. The manual requires washing hands with soap and water because alcohol-based hand rub is insufficient.",
        [kf("answer", "No"), kf("reason", "insufficient", "insuffisante")], [ev(IPC, "lavage des mains à l'eau et au savon (la solution hydro-alcoolique est insuffisante)")],
        type="direct", difficulty="easy", style="yes_no", domain="infection_control", rule="C. difficile hand hygiene", fmt="yes/no with reason", modes=["french_document"], skills=["extraction"], safety=True)

    # ---- 31. NEWS2 on hypothetical observations
    N2 = "NUR-OBS-01_NEWS2_Observation_and_Escalation_Protocol_v5"
    s1, s2, s3 = S.news2(26, 90, False, 85, 135, False, 34.8), S.news2(26, 97, False, 120, 70, True, 37.0), S.news2(16, 97, True, 120, 70, True, 37.0)
    assert (s1, s2, s3) == (18, 3, 2)
    n2ev = [ev(N2, "Respiration rate 8 or less 9-11 12-20 21-24 25 or more"), ev(N2, "SpO2 (scale 1, %) 91 or less 92-93 94-95 96 or more"),
            ev(N2, "Systolic BP (mmHg) 90 or less 91-100 101-110 111-219 220 or more"), ev(N2, "Pulse (per min) 40 or less 41-50 51-90 91-110 111-130 131 or more"),
            ev(N2, "Consciousness Alert Confusion, V, P or U"), ev(N2, "Temperature (C) 35.0 or less 35.1-36.0 36.1-38.0 38.1-39.0 39.1 or more")]
    q = main_q(31,
        "Using protocol NUR-OBS-01, calculate the NEWS2 aggregate score of a patient with respiration rate 26/min, SpO2 90% on air, systolic BP 85 mmHg, pulse 135/min, new confusion and temperature 34.8 C, and state the required response.",
        "RR 26, sats 90 on air, BP 85 systolic, pulse 135, confused, temp 34.8: what's the NEWS2 and what do we do?",
        "Every parameter scores 3 (respiration 26 = 3, SpO2 90 = 3, air = 0, systolic BP 85 = 3, pulse 135 = 3, confusion = 3, temperature 34.8 = 3): NEWS2 = 18. A score of 7 or more requires an emergency response: immediate assessment by the critical care outreach team and continuous monitoring.",
        [kf("score", "18"), kf("response", "emergency response", "emergency"), kf("team", "critical care outreach"), kf("monitoring", "continuous")],
        n2ev + [ev(N2, "7 or more emergency response: immediate assessment by the critical care outreach team continuous monitoring")],
        type="calculation", difficulty="medium", style="conditional", domain="vital_signs", rule="NEWS2 on stated observations", safety=True, fmt="score | response",
        modes=["table_in_protocol", "derived_value", "threshold_boundary"], skills=["score_from_table", "arithmetic"])
    follow_up(q, "hypothetical_variation", "A patient has respiration rate 26/min and every other parameter normal (SpO2 97% on air, systolic BP 120 mmHg, pulse 70/min, alert, temperature 37.0 C). What is the NEWS2 score and the response under NUR-OBS-01?", "What if only the respiratory rate were 26 and everything else normal?",
        "The score is 3 (respiration rate 26 = 3, all other parameters 0). A score of 3 in a single parameter requires an urgent ward-based response.",
        [kf("score", "3"), kf("response", "urgent ward-based response", "urgent ward-based")],
        [ev(N2, "Respiration rate 8 or less 9-11 12-20 21-24 25 or more"), ev(N2, "3 in a single parameter urgent ward-based response")],
        type="calculation", difficulty="hard", style="conditional", domain="vital_signs", rule="NEWS2 single-parameter trigger", safety=True, fmt="score | response",
        modes=["hypothetical_variation", "table_in_protocol", "threshold_boundary"], skills=["score_from_table", "threshold_comparison"])
    follow_up(q, "hypothetical_variation", "A patient has every parameter normal (respiration rate 16/min, SpO2 97%, systolic BP 120 mmHg, pulse 70/min, alert, temperature 37.0 C) but is receiving supplemental oxygen. What is the NEWS2 score and the response under NUR-OBS-01?", "And if everything is normal but he's on oxygen?",
        "The score is 2 (supplemental oxygen scores 2, all other parameters 0). A score of 1 to 4 requires a ward-based response: the registered nurse decides, with observations at least every 4 to 6 hours.",
        [kf("score", "2"), kf("response", "ward-based response", "ward-based"), kf("frequency", "4 to 6 hours")],
        [ev(N2, "Air or oxygen oxygen air"), ev(N2, "1 to 4 ward-based response: registered nurse decides every 4 to 6 hours")],
        type="calculation", difficulty="medium", style="conditional", domain="vital_signs", rule="NEWS2 oxygen points", safety=True, fmt="score | response",
        modes=["hypothetical_variation", "table_in_protocol"], skills=["score_from_table"])

    # ---- 32. warfarin nomogram at other INR values (Perrin)
    INR, WAR = "INR_Perrin_Josiane_2026-11-10", "PHA-ANC-03_Warfarin_Dosing_Nomogram_v3"
    pl12, pl54, pl30 = S.warfarin_plan(1.2, D(2026, 11, 10)), S.warfarin_plan(5.4, D(2026, 11, 10)), S.warfarin_plan(3.0, D(2026, 11, 10))
    assert (pl12["new_weekly"], pl12["recheck"]) == (32.2, D(2026, 11, 14)) and (pl54["new_weekly"], pl54["recheck"], pl54["omit"]) == (22.4, D(2026, 11, 11), 2)
    assert pl30["recheck"] == D(2026, 11, 10) + dt.timedelta(days=28) == D(2026, 12, 8)
    wk = ev(INR, "Dose hebdomadaire actuelle 28 mg (4 mg par jour)")
    q = main_q(32,
        "If Josiane Perrin's INR on 10/11/2026 had been 1.2, what would nomogram PHA-ANC-03 require: the action, her new weekly warfarin dose in mg and the date of the next INR?",
        "What if Mrs Perrin's INR had been 1.2 on the 10th?",
        "INR 1.2 is below 1.5: increase the weekly dose by 15%, from 28 mg to 32.2 mg per week. Next INR in 4 days, on 14/11/2026.",
        [kf("action", "increase the weekly dose by 15%", "increase weekly dose by 15%", "15%"), kf("new weekly dose", "32.2 mg", "32.2", "32,2"), kf("next INR", "14/11/2026")],
        [wk, ev(WAR, "below 1.5 increase weekly dose by 15% in 4 days")],
        type="calculation", difficulty="medium", style="conditional", domain="pharmacy", rule="Warfarin maintenance nomogram", safety=True, fmt="action | new weekly dose | next INR date",
        modes=["french_document", "hypothetical_variation", "table_in_protocol", "derived_value"], skills=["table_lookup", "percentage_change", "date_arithmetic"],
        calculation=calc({"weekly": 28, "pct": 15}, "weekly * (1 + pct / 100)", 32.2, {"weekly": (0, "28", "mg", 1), "pct": (1, "15%", "%", 1)}))
    follow_up(q, "hypothetical_variation", "And if her INR on 10/11/2026 had been 5.4: how many doses to omit, who to contact, the new weekly dose and the date of the next INR?", "And if it had been 5.4?",
        "INR 5.4 is 5.0 or above: omit two doses, contact the anticoagulation pharmacist, then decrease the weekly dose by 20%, from 28 mg to 22.4 mg per week. Next INR in 1 day, on 11/11/2026.",
        [kf("doses to omit", "omit two doses", "two doses"), kf("contact", "anticoagulation pharmacist"), kf("new weekly dose", "22.4 mg", "22.4", "22,4"), kf("next INR", "11/11/2026")],
        [wk, ev(WAR, "5.0 or above omit two doses, contact the anticoagulation pharmacist, then decrease weekly dose by 20% in 1 day")],
        type="calculation", difficulty="medium", style="conditional", domain="pharmacy", rule="Warfarin maintenance nomogram", safety=True, fmt="doses to omit | contact | new weekly dose | next INR date",
        modes=["french_document", "hypothetical_variation", "table_in_protocol", "derived_value"], skills=["table_lookup", "percentage_change", "date_arithmetic"],
        calculation=calc({"weekly": 28, "pct": 20}, "weekly * (1 - pct / 100)", 22.4, {"weekly": (0, "28", "mg", 1), "pct": (1, "20%", "%", 1)}))
    follow_up(q, "hypothetical_variation", "And if her INR on 10/11/2026 had been exactly 3.0: what does the nomogram require, and given that her record says she has been stable since September, what is the date of the next INR?", "What if it had been exactly 3.0?",
        "INR 3.0 is within 2.0 to 3.0: no change to the dose. Because she has been stable since September, the next INR is in 4 weeks, on 08/12/2026.",
        [kf("action", "no change"), kf("interval", "4 weeks"), kf("next INR", "08/12/2026")],
        [ev(WAR, "2.0 to 3.0 no change in 4 weeks if stable, otherwise 2 weeks"), ev(INR, "La patiente est stable depuis septembre.")],
        type="multi_document", difficulty="hard", style="conditional", domain="pharmacy", rule="Warfarin nomogram boundary and stability", safety=True, fmt="action | next INR date",
        modes=["french_document", "hypothetical_variation", "threshold_boundary", "multi_document_join", "derived_value"], skills=["table_lookup", "date_arithmetic", "threshold_comparison"])

    # ---- 33. discharge policy dates and an unanswerable follow-up (Martel)
    DIS, CRM, BKX = "ADM-DIS-04_Discharge_and_Transfer_of_Care_Policy_v3", "CRH_Martel_Jacques_2026-11-06", "Clinic_Bookings_Export_2026-11-19"
    dl13 = S.add_business_days(D(2026, 11, 6), 5)
    assert dl13 == D(2026, 11, 13)
    q = main_q(33,
        "Under discharge policy ADM-DIS-04, if clinic capacity did not allow Jacques Martel's (MRN 4468815) follow-up appointments to be booked before his discharge on Friday 06/11/2026, by what date at the latest should they have been booked?",
        "By when should Mr Martel's follow-ups have been booked if they couldn't be done before he left?",
        "Within 5 working days of discharge: by Friday 13/11/2026 (working days are Monday to Friday).",
        [kf("deadline", "13/11/2026"), kf("rule", "5 working days")],
        [ev(DIS, "Follow-up appointments requested on the discharge summary are booked before discharge or, if clinic capacity does not allow, within 5 working days"), ev(CRM, "Admission / discharge 02/11/2026 / 06/11/2026")],
        type="temporal", difficulty="medium", style="conditional", domain="care_transition", rule="Booking deadline in working days", fmt="date", modes=["multi_document_join", "derived_value"], skills=["business_day_arithmetic"])
    follow_up(q, "scope_change", "On what date was Jacques Martel's cardiology clinic appointment booked (created in the booking system)?", "And when was the cardiology appointment actually made?",
        "This cannot be established from the documents: the bookings export gives the date and time of each appointment, not the date on which it was booked.",
        [], [], type="negative", difficulty="medium", style="lookup", domain="care_transition", rule="Booking creation date not recorded", fmt="abstention", modes=["absence_of_document"], answerable=False, skills=["abstention"])
    follow_up(q, "drill_down", "According to ADM-DIS-04, does a booking made after the requested timeframe have to be escalated, and to whom?", "Does a late booking get escalated?",
        "Yes: a booking later than the requested timeframe is escalated to the clinic manager.",
        [kf("answer", "Yes"), kf("to whom", "clinic manager")], [ev(DIS, "a booking later than the requested timeframe is escalated to the clinic manager")],
        type="direct", difficulty="easy", style="yes_no", domain="care_transition", rule="Escalation of late bookings", fmt="yes/no | who", modes=[], skills=["extraction"])

    # ---- 34. interaction bulletin lookups
    BUL = "PHA-INT-05_Drug_Interaction_Bulletin_Q4-2026"
    irow = lambda a, b: " ".join(next(r for r in S.INTERACTIONS if r[0] == a and r[1] == b))
    dig = [r for r in S.INTERACTIONS if "Digoxin" in (r[0], r[1])]
    assert len(dig) == 4 and all(r[0] == "Digoxin" for r in dig)
    q = main_q(34,
        "List every pair involving digoxin in pharmacy interaction bulletin PHA-INT-05 with its severity.",
        "Which interactions does the pharmacy bulletin list for digoxin?",
        "Four pairs: digoxin with clarithromycin (Major), digoxin with furosemide (Moderate), digoxin with omeprazole (Minor) and digoxin with spironolactone (Minor).",
        [kf("count", "Four", "4"), kf("clarithromycin", "clarithromycin"), kf("furosemide", "furosemide"), kf("omeprazole", "omeprazole"), kf("spironolactone", "spironolactone")],
        [ev(BUL, irow("Digoxin", b)) for b in ("Clarithromycin", "Furosemide", "Omeprazole", "Spironolactone")],
        type="table", difficulty="medium", style="list", domain="medication_safety", rule="Filter the bulletin on one drug", fmt="list of pairs with severity", modes=["table_in_protocol", "deep_in_report"], skills=["filtering"], safety=True)
    follow_up(q, "drill_down", "What management does bulletin PHA-INT-05 advise for the Moderate digoxin pair?", "What does it say for the moderate one?",
        "Digoxin with furosemide: hypokalaemia raises digoxin toxicity; check potassium weekly.",
        [kf("pair", "furosemide"), kf("management", "check potassium weekly")], [ev(BUL, irow("Digoxin", "Furosemide"))],
        type="direct", difficulty="easy", style="lookup", domain="medication_safety", rule="Management of a Moderate pair", fmt="management", modes=["table_in_protocol"], skills=["extraction"], safety=True)
    follow_up(q, "scope_change", "Which pairs involving warfarin are rated Major in bulletin PHA-INT-05, and what does it advise for each?", "And the major ones with warfarin?",
        "Warfarin with clarithromycin: avoid; if essential check INR within 3 days. Warfarin with amiodarone: reduce the warfarin dose by about a third and check INR weekly.",
        [kf("pair 1", "clarithromycin"), kf("action 1", "within 3 days"), kf("pair 2", "amiodarone"), kf("action 2", "check INR weekly")],
        [ev(BUL, irow("Warfarin", "Clarithromycin")), ev(BUL, irow("Warfarin", "Amiodarone"))],
        type="multi_evidence", difficulty="medium", style="list", domain="medication_safety", rule="Major pairs for one drug", fmt="pairs with advice", modes=["table_in_protocol"], skills=["filtering", "extraction"], safety=True)
