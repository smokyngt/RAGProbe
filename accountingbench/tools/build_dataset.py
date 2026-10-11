#!/usr/bin/env python3
"""Build the 20 AccountingBench questions (FinanceBench JSON format) from world.py and the generated corpus.

    python accountingbench/tools/build_dataset.py
      -> datasets/accountingbench_v1.jsonl          the benchmark (full annotation, same schema as FinanceBench)
         datasets/accountingbench_v1_simple.jsonl/.csv  question / answer / documents / pages, for an external runner
         datasets/anomaly_register.json             every planted anomaly, its documents and the questions that test it

Expected answers are COMPUTED from the world model (never typed by hand) and asserted against the values the scenario
was designed with. Evidence quotes are full lines of the cited page as extracted by `pdftotext -layout` (for scanned
documents: from corpus/ocr_reference/, the text the scan was made from), so they are verbatim by construction.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import D, ROOT, accept_amount, date, fdate, fmt  # noqa: E402
from world import (LME_NEW_IBAN, OUTSIDE_PAYEES, RANK, SUPPLIERS, build_world, journal,  # noqa: E402
                   ledger_balance, open_items, required_approver, september_journal)

MANIFEST = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
BY_KEY = {d["key"]: d for d in MANIFEST["documents"]}
_PAGES: dict[str, list[str]] = {}
SEP_END = date(30, 9)


def pages_of(doc_id: str) -> list[str]:
    if doc_id not in _PAGES:
        d = next(x for x in MANIFEST["documents"] if x["document_id"] == doc_id)
        if d["scanned"]:
            text = (ROOT / "corpus" / "ocr_reference" / f"{doc_id}.txt").read_text("utf-8")
        else:
            text = subprocess.run(["pdftotext", "-layout", str(ROOT / "corpus" / "documents" / d["filename"]), "-"],
                                  capture_output=True, text=True, check=True).stdout
        pages = text.split("\f")
        _PAGES[doc_id] = pages[:-1] if pages and pages[-1] == "" else pages
    return _PAGES[doc_id]


def did(key: str) -> str:
    return BY_KEY[key]["document_id"]


def ev(key: str, *needles) -> list[dict]:
    """Evidence items for a document: the full (whitespace-normalised) lines containing each needle.

    A needle is a string or a tuple of strings that must all be on the same line. Lines are grouped per page and kept
    in reading order, joined with ' … ' (the FinanceBench fragment separator)."""
    doc_id = did(key)
    pages = pages_of(doc_id)
    hits: dict[int, list[tuple[int, str]]] = {}
    for nd in needles:
        parts = nd if isinstance(nd, tuple) else (nd,)
        found = None
        for p, text in enumerate(pages, 1):
            for ln, line in enumerate(text.splitlines()):
                if all(x in line for x in parts):
                    found = (p, ln, " ".join(line.split()))
                    break
            if found:
                break
        if not found:
            raise SystemExit(f"evidence not found in {key} ({doc_id}): {parts}")
        p, ln, line = found
        if (ln, line) not in hits.setdefault(p, []):
            hits[p].append((ln, line))
    return [{"document_id": doc_id, "page": p, "text": " … ".join(l for _, l in sorted(v))} for p, v in sorted(hits.items())]


def kf(fact: str, value, extra=()) -> dict:
    if isinstance(value, Decimal):
        forms = accept_amount(value)
        return {"fact": fact, "value": forms[0], "accept": forms[1:] + list(extra)}
    if isinstance(value, dt.date):
        return {"fact": fact, "value": fdate(value), "accept": [value.isoformat(), fdate(value, "dot"), fdate(value, "long")]}
    return {"fact": fact, "value": str(value), "accept": list(extra)}


def e(x: Decimal) -> str:
    return fmt(x, "en")


def src(raw: str, idx: int, unit: str = "EUR") -> dict:
    return {"evidence_index": idx, "raw": raw, "unit": unit, "scale": 1.0}


def F(x: Decimal) -> str:  # as printed in French-format documents
    return fmt(x, "fr")


def calc_from(values: dict, operation: str, result: Decimal, idx: int = 0) -> dict:
    """Calculation block whose inputs are all printed (French format) in evidence item `idx`."""
    return {"inputs": {k: float(v) for k, v in values.items()}, "operation": operation, "result": float(result),
            "input_sources": {k: src(F(v), idx) for k, v in values.items()}}


QUESTIONS: list[dict] = []
ANOMALIES: list[dict] = []


def Q(**kw):
    QUESTIONS.append(kw)


def main() -> int:
    w = build_world()
    pos = w.pos
    sj = september_journal(w)
    inv = w.inv
    sep_pay = [x for x in w.payments if x.date.month == 9]
    po_num = {k: v.number for k, v in pos.items()}

    # ============================================================== B1 duplicates in the September purchase journal
    seen, dups = {}, []
    for piece, d, i in sj:
        keys = [(i.sup, i.number), (i.sup, i.date, i.total)]
        first = next((seen[k] for k in keys if k in seen), None)
        if first:
            dups.append((first, (piece, d, i)))
        for k in keys:
            seen.setdefault(k, (piece, d, i))
    assert [(a[0], b[0], b[2].number) for a, b in dups] == [("AC-2609-007", "AC-2609-022", "FA-2026-0917")], dups
    cas917 = inv("FA-2026-0917")
    Q(pilot="B1", type="table", style="list", difficulty="easy", topic="ap:duplicate_invoices",
      failure_modes=["similar_table_labels"],
      control="Duplicate invoice detection in the purchase journal",
      rule="Two journal lines are duplicates when they have the same supplier and the same invoice number, or the same "
           "supplier, the same invoice date and the same amount including VAT.",
      question="In the September 2026 purchase journal (journal AC) of Azur Marine Services S.A.M., identify every supplier "
               "invoice recorded more than once. Rule: two journal lines are duplicates when they have the same supplier "
               "and the same invoice number, or the same supplier, the same invoice date and the same amount including VAT. "
               "For each duplicate give the supplier, the invoice number, the amount including VAT, the piece number and "
               "booking date of each journal line, and the amount that would be paid twice if both lines were paid. If "
               "there is no duplicate, say so.",
      natural="Is any supplier invoice booked twice in the September 2026 purchase journal?",
      answer=f"One duplicate. Côte d'Azur Ship Chandlers SAS invoice FA-2026-0917 (EUR {e(cas917.total)} incl. VAT) is booked "
             f"twice in the September 2026 purchase journal: piece AC-2609-007 on 03/09/2026 and piece AC-2609-022 on "
             f"22/09/2026. If both lines were paid, EUR {e(cas917.total)} would be paid twice. No other line meets the rule "
             f"(the monthly berth, telecom and waste invoices have different numbers or dates).",
      key_facts=[kf("duplicated invoice", "FA-2026-0917"), kf("first journal piece", "AC-2609-007"),
                 kf("second journal piece", "AC-2609-022"), kf("amount at risk", cas917.total)],
      evidence=ev("journal:9", ("AC-2609-007", "FA-2026-0917"), ("AC-2609-022", "FA-2026-0917")),
      output_format="table: supplier | invoice number | amount incl. VAT | piece 1 / date | piece 2 / date | amount paid twice",
      anomalies=["A01"])

    # ============================================================== B2 invoices settled by several debits in September
    multi = {}
    for x in sep_pay:
        for num, a in x.settles:
            multi.setdefault(num, []).append((x, a))
    multi = {k: v for k, v in multi.items() if len(v) > 1}
    assert list(multi) == ["INV-2026-0371"], multi
    m371 = inv("INV-2026-0371")
    (p1, a1), (p2, a2) = sorted(multi["INV-2026-0371"], key=lambda t: t[0].date)
    assert a1 + a2 == m371.total == D("11580.00")
    evb = ev("bank:2026-09", ("MEDITERRA", "0371 1/2"), ("MEDITERRA", "0371 2/2"))
    evi = ev("inv:INV-2026-0371", ("TOTAL EUR", e(m371.total)))
    Q(pilot="B2", type="multi_document", style="list", difficulty="easy", topic="ap:instalments",
      failure_modes=["multi_evidence_combination"], control="Invoices settled in several instalments",
      rule="An invoice is settled by instalments when two or more separate September debits refer to it.",
      question="Using the September 2026 bank statement of Azur Marine Services S.A.M. (Banque Riviera Monaco), list every "
               "supplier invoice that was settled by two or more separate debits during September 2026. For each, give the "
               "supplier, the invoice number, the invoice amount including VAT, the date and amount of each debit, and "
               "whether the invoice is fully settled at 30/09/2026 (YES/NO).",
      natural="Which supplier invoices were paid in several instalments in September 2026?",
      answer=f"Only Mediterra Marine Supplies S.A.M. invoice INV-2026-0371 (EUR {e(m371.total)} incl. VAT) was settled by "
             f"two debits: EUR {e(a1)} on {fdate(p1.date)} and EUR {e(a2)} on {fdate(p2.date)}. Together they equal the "
             f"invoice amount, so the invoice is fully settled at 30/09/2026: YES.",
      key_facts=[kf("invoice", "INV-2026-0371"), kf("instalment amount", a1), kf("first debit date", p1.date),
                 kf("second debit date", p2.date), kf("fully settled", "YES", ["fully settled"])],
      evidence=evb + evi,
      calculation={"inputs": {"debit_1": float(a1), "debit_2": float(a2)}, "operation": "debit_1 + debit_2",
                   "result": float(a1 + a2),
                   "input_sources": {"debit_1": src(F(a1), 0), "debit_2": src(F(a2), 0)}},
      output_format="table: supplier | invoice | amount incl. VAT | debit dates and amounts | fully settled (YES/NO)",
      anomalies=[])

    # ============================================================== B3 PO approval matrix
    sep_pos = sorted([p for p in pos.values() if p.date.month == 9], key=lambda p: p.number)
    gaps = [p for p in sep_pos if RANK[p.approver] < RANK[required_approver(p.net)]]
    assert len(sep_pos) == 10 and [p.key for p in gaps] == ["nts_sep", "eco_sep"], [p.key for p in gaps]
    nts, eco = pos["nts_sep"], pos["eco_sep"]
    Q(pilot="B3", type="multi_document", style="list", difficulty="medium", topic="ap:approval",
      failure_modes=["multi_evidence_combination", "header_dependency"], control="PO approval against the approval matrix",
      rule="Approval matrix of policy PRC-FIN-04 on the net PO amount; a higher level may approve a lower amount.",
      question="Check every purchase order issued by Azur Marine Services S.A.M. and dated between 01/09/2026 and "
               "30/09/2026 against the approval matrix of policy PRC-FIN-04 (net amount excluding VAT: up to EUR 5,000.00 "
               "-> Operations Manager; EUR 5,000.01 to 20,000.00 -> Finance Director; above EUR 20,000.00 -> Chief "
               "Executive Officer; a higher level may approve a lower amount). State how many September purchase orders "
               "you checked, then list only those approved below the required level, with PO number, supplier, net amount, "
               "approver named on the PO and required approver.",
      natural="Were any September 2026 purchase orders approved by someone below the required approval level?",
      answer=f"10 purchase orders dated September 2026 were checked. Two were approved below the required level: "
             f"{nts.number} (NavTech Systems GmbH, EUR {e(nts.net)} net) approved by Claire Martin, Finance Director, "
             f"whereas above EUR 20,000.00 the Chief Executive Officer must approve; and {eco.number} (EcoMarine Waste "
             f"Services SAS, EUR {e(eco.net)} net) approved by Thomas Rinaldi, Operations Manager, whereas between "
             f"EUR 5,000.01 and 20,000.00 the Finance Director must approve. The other 8 are correctly approved.",
      key_facts=[kf("POs checked", "10"), kf("NavTech PO", nts.number), kf("NavTech PO net", nts.net),
                 kf("required approver NavTech", "Chief Executive Officer", ["CEO"]), kf("EcoMarine PO", eco.number),
                 kf("EcoMarine PO net", eco.net), kf("required approver EcoMarine", "Finance Director")],
      evidence=ev(f"po:{nts.number}", ("TOTAL NET AMOUNT", e(nts.net)), ("Approved by", "Claire Martin"))
      + ev(f"po:{eco.number}", ("TOTAL NET AMOUNT", e(eco.net)), ("Approved by", "Thomas Rinaldi"))
      + ev("policy:procurement", "up to 5,000.00", "5,000.01 to 20,000.00", "above 20,000.00"),
      output_format="count of POs checked; table: PO | supplier | net amount | approver on PO | required approver",
      anomalies=["A07", "A08"])

    # ============================================================== B4 unmatched debits
    unmatched = [x for x in sep_pay if not x.settles]
    assert [(x.date, x.amount) for x in unmatched] == [(date(25, 9), D("3750.00")), (date(29, 9), D("1980.00"))]
    u1, u2 = unmatched
    batch_keys = {dt.date.fromisoformat(v["document_date"]): k for k, v in BY_KEY.items() if k.startswith("batch:")}
    Q(pilot="B4", type="multi_document", style="list", difficulty="medium", topic="bank:unmatched",
      failure_modes=["similar_table_labels", "multi_evidence_combination"], control="Unmatched bank debits",
      rule="A debit is matched when its statement label or the payment execution notice cites the number of an invoice, "
           "credit note or purchase order of the same payee that is in the file, whatever the amount (partial and short "
           "payments are matched). Payroll, social contributions, VAT and bank charges are out of scope.",
      question="On the September 2026 bank statement of Azur Marine Services S.A.M., consider every debit except payroll "
               "(SALAIRES), social contributions (COTISATIONS SOCIALES), VAT payments (PAIEMENT TVA) and bank charges "
               "(FRAIS, ABONNEMENT, COMMISSIONS). A debit is matched when its statement label or the payment execution "
               "notice cites the number of an invoice, credit note or purchase order of the same payee that is in the file, "
               "whatever the amount (partial or short payments count as matched). List the debits that cannot be matched with their "
               "date, statement label and amount, give the beneficiary shown on the bank's payment execution notice, and "
               "give their total. Do not guess what they relate to.",
      natural="Which September 2026 bank debits have no supporting invoice?",
      answer=f"Two debits cannot be matched to any invoice, credit note or purchase order: (1) {fdate(u1.date)}, "
             f"\"{u1.label}\", EUR {e(u1.amount)}, beneficiary DUBOIS JULIEN; (2) {fdate(u2.date)}, \"{u2.label}\", "
             f"EUR {e(u2.amount)}, beneficiary BLUEWATER CONSULTING SARL. Total EUR {e(u1.amount + u2.amount)}. Neither "
             f"beneficiary is in the supplier master file and no document in the file explains them.",
      key_facts=[kf("unmatched debit 1", u1.amount), kf("reference 1", "MISC REF 0925-77"),
                 kf("unmatched debit 2", u2.amount), kf("beneficiary 2", "BLUEWATER CONSULTING", ["Bluewater"]),
                 kf("total unmatched", u1.amount + u2.amount)],
      evidence=ev("bank:2026-09", "MISC REF 0925-77", "BLUEWATER") + ev(batch_keys[u1.date], "DUBOIS JULIEN")
      + ev(batch_keys[u2.date], "BLUEWATER CONSULTING SARL"),
      calculation={"inputs": {"debit_misc": float(u1.amount), "debit_bluewater": float(u2.amount)},
                   "operation": "debit_misc + debit_bluewater", "result": float(u1.amount + u2.amount),
                   "input_sources": {"debit_misc": src(F(u1.amount), 0), "debit_bluewater": src(F(u2.amount), 0)}},
      output_format="table: date | label | amount | beneficiary; total",
      anomalies=["A13", "A14"])

    # ============================================================== B5 document types (Oceanic Safety)
    o552 = inv("INV-2026-552")
    Q(pilot="B5", type="multi_document", style="list", difficulty="easy", topic="ap:document_types",
      failure_modes=["terminology_mismatch", "multiple_entities"], control="Document type and liability recognition",
      rule="Only an invoice (or credit note) addressed to the company creates (or reduces) an accounts payable liability.",
      question="The file contains several documents issued by Oceanic Safety Europe GmbH about the 2026 replenishment of "
               "safety equipment for M/Y Aurelia (e-mails excluded). List each with its type (quotation, pro-forma "
               "invoice, delivery note, invoice, credit note, statement of account) and number, and the purchase order "
               "Azur Marine Services S.A.M. issued for it. Then state which document(s) must be recorded as a liability in "
               "the accounts payable ledger at 30/09/2026 and for what amount.",
      natural="Which Oceanic Safety documents should be recorded as a payable at 30 September 2026?",
      answer=f"Oceanic Safety Europe GmbH documents: quotation OSE-Q-2026-118 (12/08/2026), pro-forma invoice "
             f"OSE-PF-2026-044 (20/08/2026), delivery note OSE-LS-26-0907 (07/09/2026), invoice INV-2026-552 "
             f"(12/09/2026) and a statement of account at 30/09/2026; Azur Marine Services issued purchase order "
             f"{po_num['ose_aug']}. Only invoice INV-2026-552 is recorded as a liability: EUR {e(o552.total)} (intra-EU "
             f"supply, reverse charge, no VAT invoiced). The quotation, pro-forma, purchase order, delivery note and "
             f"statement create no additional liability (the statement only confirms the EUR {e(o552.total)} balance).",
      key_facts=[kf("liability document", "INV-2026-552"), kf("liability amount", o552.total),
                 kf("pro-forma not a liability", "OSE-PF-2026-044"), kf("quotation", "OSE-Q-2026-118")],
      evidence=ev("inv:INV-2026-552", ("Invoice No.", "INV-2026-552"), ("TOTAL EUR", "6.200,00"))
      + ev("pf:OSE-PF-2026-044", "NOT A TAX INVOICE") + ev("quote:OSE-Q-2026-118", ("Number", "OSE-Q-2026-118")),
      output_format="table: document type | number | date | liability at 30/09 (YES/NO) | amount",
      anomalies=[])

    # ============================================================== T1 Côte d'Azur Ship Chandlers documents
    c948, c931 = inv("FA-2026-0948"), inv("FA-2026-0931")
    Q(pilot="T1", type="multi_document", style="list", difficulty="medium", topic="ap:document_relevance",
      failure_modes=["multiple_entities", "similar_table_labels"], control="Relevance and status of supplier documents",
      rule="BOOK = valid invoice of the company, booked once; DUPLICATE = copy of an invoice already in the file; "
           "OTHER ENTITY = addressed to another company.",
      question="For the supplier Côte d'Azur Ship Chandlers SAS, review every invoice document in the file dated between "
               "01/09/2026 and 30/09/2026, including copies. Give each document exactly one status: BOOK (a valid invoice "
               "of Azur Marine Services S.A.M., to be recorded once), DUPLICATE (a copy of an invoice already in the file, "
               "not to be recorded again) or OTHER ENTITY (addressed to another company). Then say whether the September "
               "2026 purchase journal (AC) is consistent with these statuses and quantify any difference.",
      natural="Which Côte d'Azur Ship Chandlers invoices from September 2026 should actually be booked?",
      answer=f"Four documents: (1) invoice FA-2026-0917 of 03/09/2026, EUR {e(cas917.total)}: BOOK; (2) a copy of the same "
             f"invoice FA-2026-0917 marked DUPLICATA, sent on 21/09/2026: DUPLICATE; (3) invoice FA-2026-0948 of "
             f"24/09/2026, EUR {e(c948.total)}: BOOK; (4) invoice FA-2026-0931 of 15/09/2026, EUR {e(c931.total)}, "
             f"addressed to Azur Marine Charter SARL (Antibes): OTHER ENTITY. The September journal is not consistent: "
             f"FA-2026-0917 is booked twice (AC-2609-007 and AC-2609-022), overstating purchases and payables by "
             f"EUR {e(cas917.total)} incl. VAT (EUR {e(cas917.net)} net). FA-2026-0931 is correctly not booked.",
      key_facts=[kf("duplicate copy", "DUPLICATE", ["DUPLICATA"]), kf("other entity invoice", "FA-2026-0931"),
                 kf("other entity", "Azur Marine Charter"), kf("valid invoice", "FA-2026-0948"),
                 kf("overstatement", cas917.total)],
      evidence=ev("inv:FA-2026-0917", ("Facture n°", "FA-2026-0917"))
      + ev("inv:FA-2026-0917:duplicata", ("Facture n°", "FA-2026-0917"), "Duplicata")
      + ev("inv:FA-2026-0931", "Azur Marine Charter SARL") + ev("inv:FA-2026-0948", ("Facture n°", "FA-2026-0948"))
      + ev("journal:9", ("AC-2609-007", "FA-2026-0917"), ("AC-2609-022", "FA-2026-0917")),
      output_format="table: document | date | amount | status (BOOK / DUPLICATE / OTHER ENTITY); journal consistency",
      anomalies=["A01"])

    # ============================================================== T2 Mediterra statement reconciliation
    m418 = inv("INV-2026-0418")
    bal_med = ledger_balance(w, "MED", SEP_END)
    assert bal_med == 0 and m418.total == D("15360.00")
    Q(pilot="T2", type="multi_document", style="explanatory", difficulty="medium", topic="ap:supplier_statement",
      failure_modes=["multi_evidence_combination", "terminology_mismatch"], control="Supplier statement reconciliation",
      rule="Difference = balance per supplier statement - balance per ledger, explained item by item.",
      question="Reconcile the statement of account sent by Mediterra Marine Supplies S.A.M. at 30/09/2026 with supplier "
               "account 401MED in the accounts payable ledger (grand-livre fournisseurs) of Azur Marine Services S.A.M. at "
               "the same date. Give the balance per supplier statement, the balance per ledger, the difference, and each "
               "document that explains the difference with its date, amount and the date Azur Marine Services received it. "
               "Say whether the explaining item relates to September 2026.",
      natural="Why does Mediterra's statement at 30 September 2026 not agree with our ledger?",
      answer=f"Balance per Mediterra statement at 30/09/2026: EUR {e(m418.total)}. Balance of account 401MED at 30/09/2026: "
             f"EUR 0.00 (invoice INV-2026-0371 was settled by the two instalments of 10/09 and 24/09). Difference: "
             f"EUR {e(m418.total)}, fully explained by invoice INV-2026-0418 dated 30/09/2026 (EUR {e(m418.net)} net + "
             f"EUR {e(m418.vat)} VAT), received on 02/10/2026 (RECEIVED stamp and Mediterra e-mail of 02/10/2026) and "
             f"therefore not in the September journal. It relates to September 2026: the goods were delivered on "
             f"25/09/2026 (delivery note MMS-DN-26-0925), so it must be accrued at 30/09/2026.",
      key_facts=[kf("statement balance", m418.total), kf("ledger balance", "0.00", ["nil", "zero", "0,00"]),
                 kf("explaining invoice", "INV-2026-0418"), kf("received date", date(2, 10)),
                 kf("relates to September", "accrued", ["accrue", "accrual"])],
      evidence=ev("stmt:MED", "Balance due at", ("30/09/2026", "INV-2026-0418"))
      + ev("ledger:9", "401MED", "Total compte 401MED")
      + ev("inv:INV-2026-0418", "RECEIVED 02/10/2026", ("Invoice date", "30/09/2026"))
      + ev("dn:MMS-DN-26-0925", ("Date", "25/09/2026")),
      calculation={"inputs": {"statement_balance": float(m418.total), "ledger_balance": 0.0},
                   "operation": "statement_balance - ledger_balance", "result": float(m418.total),
                   "input_sources": {"statement_balance": src("15,360.00", 0), "ledger_balance": src("0,00", 1)}},
      output_format="statement balance | ledger balance | difference | explaining items (document, date, amount, received)",
      anomalies=["A15"])

    # ============================================================== T3 bank matching for six suppliers
    six = ["MED", "SEA", "HAR", "MFS", "RVE", "CAS"]
    rows = {}
    for x in sep_pay:
        if x.payee in six:
            for num, a in x.settles:
                rows.setdefault(num, [])
    for num in rows:
        i = inv(num)
        cns = sum((c.total for c in w.invoices if c.kind == "credit_note" and c.ref_invoice == num), D(0))
        paid = [(x.date, a) for x in w.payments if x.date <= SEP_END for n2, a in x.settles if n2 == num]
        rows[num] = dict(sup=i.s.name, due=i.total - cns, paid=paid, total_paid=sum((a for _, a in paid), D(0)))
    order = ["INV-2026-0371", "SG-2026/0877", "HP-26-1450", "INV-2026-1074", "INV-2026-1182", "RE-2026-0733",
             "FA-2026-0851", "FA-2026-0917"]
    assert sorted(rows) == sorted(order), sorted(rows)
    tot_due = sum((rows[n]["due"] for n in order), D(0))
    tot_paid = sum((rows[n]["total_paid"] for n in order), D(0))
    assert (tot_due, tot_paid) == (D("88472.00"), D("63334.00"))
    lines = []
    exp_rows = []
    for n in order:
        r = rows[n]
        bal = r["due"] - r["total_paid"]
        st = "SETTLED" if bal == 0 else ("PARTIALLY SETTLED" if bal > 0 else "OVERPAID")
        paid_s = " + ".join(f"EUR {e(a)} on {fdate(d)}" for d, a in r["paid"])
        lines.append(f"{r['sup']} {n}: due EUR {e(r['due'])}, paid {paid_s}, balance EUR {e(bal)}, {st}")
        exp_rows.append({"invoice": n, "amount_due": str(r["due"]), "amount_paid": str(r["total_paid"]), "balance": str(bal),
                         "status": st})
    Q(pilot="T3", type="multi_document", style="list", difficulty="hard", topic="bank:reconciliation",
      failure_modes=["multi_evidence_combination", "similar_table_labels", "multiple_entities"],
      control="Bank-to-invoice matching (lettrage) for named suppliers",
      rule="Amount due = invoice total incl. VAT minus credit notes referring to it; amount paid = all debits referring to "
           "the invoice or its PO (July–September 2026). SETTLED / PARTIALLY SETTLED / OVERPAID.",
      question="Match the September 2026 bank statement of Azur Marine Services S.A.M. with supplier invoices for these six "
               "suppliers only: Mediterra Marine Supplies, SeaGlass Coatings, Harbor Parts, Marina Fuel Services, Riviera "
               "Electronics and Côte d'Azur Ship Chandlers. Scope: every invoice of these suppliers for which at least one "
               "debit appears on the September statement. Amount due = invoice total including VAT minus any credit note "
               "referring to it. Amount paid = all debits (July to September 2026) referring to the invoice or to its "
               "purchase order. Status: SETTLED (paid = due), PARTIALLY SETTLED (paid < due) or OVERPAID (paid > due). Give "
               "one row per invoice (supplier, invoice number, amount due, payments with dates, balance, status), then the "
               "totals of amount due, amount paid and balance.",
      natural="Which invoices from our six main suppliers paid in September 2026 are fully settled?",
      answer="Eight invoices are in scope. " + "; ".join(lines) + f". Totals: amount due EUR {e(tot_due)}, amount paid "
             f"EUR {e(tot_paid)}, balance EUR {e(tot_due - tot_paid)} (SeaGlass EUR 10.00 short after credit note "
             f"SG-CN-2026/0112, Marina Fuel EUR 13,200.00 outstanding, Riviera Electronics EUR 11,928.00 balance after the "
             f"contractual deposit).",
      key_facts=[kf("SeaGlass balance", D("10.00"), ["EUR 10"]), kf("Marina Fuel 1182 balance", D("13200.00")),
                 kf("Riviera balance", D("11928.00")), kf("total due", tot_due), kf("total paid", tot_paid),
                 kf("total balance", tot_due - tot_paid), kf("Mediterra settled", "INV-2026-0371")],
      evidence=ev("bank:2026-09", "INV-2026-0371 1/2", "INV-2026-0371 2/2", "SG-2026/0877 LESS CN0112", "HP-26-1450",
                  "INV-2026-1074", "INV 1182", "ACOMPTE 30%", "FA-2026-0851", "FA-2026-0917")
      + ev("inv:SG-CN-2026/0112", ("TOTAL EUR", "620.00"))
      + ev("inv:SG-2026/0877", ("TOTAL EUR", "8,460.00"))
      + ev("inv:INV-2026-1182", ("TOTAL EUR", "26,400.00"))
      + ev("inv:RE-2026-0733", ("Total TTC", "17 040,00"), ("NET À PAYER", "11 928,00")),
      calculation=None,
      output_format="table: supplier | invoice | amount due | payments (date, amount) | balance | status; totals",
      anomalies=["A02", "A03"], expected_rows=exp_rows)

    # ============================================================== T4 SeaGlass short payment
    s877, cn = inv("SG-2026/0877"), inv("SG-CN-2026/0112")
    psea = next(x for x in sep_pay if x.payee == "SEA")
    diff = s877.total - cn.total - psea.amount
    assert diff == D("10.00") and ledger_balance(w, "SEA", SEP_END) == D("10.00")
    Q(pilot="T4", type="calculation", style="explanatory", difficulty="medium", topic="ap:payment_discrepancy",
      failure_modes=["multi_evidence_combination"], control="Payment discrepancy after a credit note",
      rule="Net due = invoice - credit note; difference = net due - payment.",
      question="For SeaGlass Coatings S.r.l. invoice SG-2026/0877, compute the amount due after the credit note that refers "
               "to it and compare it with the payment made in September 2026. Give the invoice amount, the credit note "
               "number and amount, the net amount due, the payment date and amount, and the difference. Then state (a) "
               "whether this difference appears as an open balance on supplier account 401SEA in the accounts payable "
               "ledger at 30/09/2026, and (b) whether any document in the file explains or waives it (YES with the "
               "document / NO).",
      natural="Was the SeaGlass invoice fully paid after the credit note?",
      answer=f"Invoice SG-2026/0877: EUR {e(s877.total)}. Credit note SG-CN-2026/0112 of 02/09/2026: EUR {e(cn.total)}. Net "
             f"amount due: EUR {e(s877.total - cn.total)}. Payment on 15/09/2026: EUR {e(psea.amount)}. Difference: "
             f"EUR {e(diff)} short-paid. (a) Yes: account 401SEA shows a credit balance of EUR {e(diff)} at 30/09/2026. "
             f"(b) NO: no document explains or waives the EUR {e(diff)}; SeaGlass's own e-mail of 02/09/2026 states a "
             f"balance due of EUR 7,840.00. The invoice is not fully settled.",
      key_facts=[kf("net due", s877.total - cn.total), kf("payment", psea.amount), kf("difference", diff, ["EUR 10"]),
                 kf("credit note", "SG-CN-2026/0112"), kf("ledger shows balance", "401SEA"),
                 kf("no explaining document", "NO", ["no document"])],
      evidence=ev("inv:SG-2026/0877", ("TOTAL EUR", "8,460.00")) + ev("inv:SG-CN-2026/0112", ("TOTAL EUR", "620.00"))
      + ev("bank:2026-09", "SG-2026/0877 LESS CN0112") + ev("ledger:9", "Total compte 401SEA"),
      calculation={"inputs": {"invoice": float(s877.total), "credit_note": float(cn.total), "payment": float(psea.amount)},
                   "operation": "invoice - credit_note - payment", "result": float(diff),
                   "input_sources": {"invoice": src("8,460.00", 0), "credit_note": src("620.00", 1),
                                     "payment": src("7 830,00", 2)}},
      output_format="invoice | credit note | net due | payment | difference | ledger balance (YES/NO) | explaining document",
      anomalies=["A02"])

    # ============================================================== T5 aged payables > 60 days
    old = [(i, a, (SEP_END - i.due).days) for i, a, k in open_items(w, SEP_END) if (SEP_END - i.due).days > 60]
    old.sort(key=lambda t: -t[2])
    assert [(i.number, d) for i, _, d in old] == [("KIT-2026-0602", 91), ("NYS-2026-071", 80)]
    tot_old = sum((a for _, a, _ in old), D(0))
    Q(pilot="T5", type="multi_document", style="list", difficulty="medium", topic="ap:aged_payables",
      failure_modes=["header_dependency", "similar_table_labels"], control="Aged payables review",
      rule="Items in the 61-90 days and over 90 days buckets of the aged payables report at 30/09/2026.",
      question="According to the aged payables report (balance âgée fournisseurs) of Azur Marine Services S.A.M. at "
               "30/09/2026, list every invoice more than 60 days past due, with supplier, invoice number, due date, days "
               "past due at 30/09/2026 and amount, and give their total. For each, state whether a document in the file "
               "shows that the invoice is disputed (YES with the document / NO).",
      natural="Which supplier invoices are more than 60 days overdue at 30 September 2026?",
      answer=f"Two invoices, total EUR {e(tot_old)}: Kairos IT Services SAS KIT-2026-0602, due 01/07/2026, 91 days past "
             f"due, EUR 1,320.00, disputed: YES (e-mail of 03/07/2026 from Claire Martin rejecting the 11 additional hours "
             f"as included in the fixed fee of agreement MSA-2022-07, schedule B); Northstar Yacht Services SARL "
             f"NYS-2026-071, due 12/07/2026, 80 days past due, EUR 2,280.00, disputed: NO.",
      key_facts=[kf("Kairos invoice", "KIT-2026-0602"), kf("Kairos amount", D("1320.00")), kf("Kairos days", "91"),
                 kf("Northstar invoice", "NYS-2026-071"), kf("Northstar amount", D("2280.00")), kf("Northstar days", "80"),
                 kf("total > 60 days", tot_old)],
      evidence=ev("aged:0930", "KIT-2026-0602", "NYS-2026-071") + ev("mail:kairos_dispute", "We do not accept invoice"),
      calculation={"inputs": {"kairos": 1320.0, "northstar": 2280.0}, "operation": "kairos + northstar",
                   "result": float(tot_old), "input_sources": {"kairos": src("1 320,00", 0), "northstar": src("2 280,00", 0)}},
      output_format="table: supplier | invoice | due date | days past due | amount | disputed (YES/NO, document); total",
      anomalies=[])

    # ============================================================== T6 Marina Fuel partial payment
    m1182 = inv("INV-2026-1182")
    pm = next(x for x in sep_pay if x.ref == "INV 1182")
    later = [x for x in w.payments if x.payee == "MFS" and x.date > SEP_END]
    assert not later and m1182.total - pm.amount == D("13200.00")
    Q(pilot="T6", type="multi_document", style="explanatory", difficulty="medium", topic="ap:partial_payment",
      failure_modes=["multi_evidence_combination", "terminology_mismatch"], control="Partial payment follow-up",
      rule="Answer YES only if a document provides for a payment schedule or an allocation between vessels; otherwise "
           "NO DOCUMENT FOUND, listing the documents consulted.",
      question="For Azur Marine Services S.A.M., match Marina Fuel Services S.A.M. invoice INV-2026-1182 with the bank "
               "statements of September 2026 and of 1-9 October 2026. Give the invoice amount including VAT, each payment "
               "(value date, statement label, amount) and the balance still due with its due date. Then say whether any "
               "document in the file (purchase order, delivery note, invoice, e-mail) provides for a payment schedule or an "
               "allocation of this invoice between two vessels: answer YES with the source, or NO DOCUMENT FOUND with the "
               "list of documents you consulted.",
      natural="Is the rest of Marina Fuel invoice 1182 still to be paid, or was it meant to be split?",
      answer=f"Invoice INV-2026-1182 of 12/09/2026: EUR {e(m1182.total)} incl. VAT (11,000 L of MGO for M/Y Aurelia). One "
             f"payment: value date 22/09/2026, \"{pm.label}\", EUR {e(pm.amount)}. No further payment up to 09/10/2026. "
             f"Balance still due: EUR {e(m1182.total - pm.amount)}, due on {fdate(m1182.due)}. NO DOCUMENT FOUND providing "
             f"for a schedule or a split between vessels: purchase order {po_num['mfs_sep']} (single delivery by road "
             f"tanker), bunker delivery note MFS-BDN-26-0911 (one delivery, M/Y Aurelia), the invoice and the accounting "
             f"e-mail of 28/09/2026 (an unanswered question) were consulted.",
      key_facts=[kf("invoice total", m1182.total), kf("payment", pm.amount), kf("payment date", date(22, 9)),
                 kf("balance due", m1182.total - pm.amount), kf("no document", "NO DOCUMENT FOUND", ["no document"])],
      evidence=ev("inv:INV-2026-1182", ("TOTAL EUR", "26,400.00")) + ev("bank:2026-09", "INV 1182")
      + ev(f"po:{po_num['mfs_sep']}", "Single delivery by road tanker") + ev("dn:MFS-BDN-26-0911", ("Vessel", "Aurelia")),
      calculation={"inputs": {"invoice": float(m1182.total), "payment": float(pm.amount)}, "operation": "invoice - payment",
                   "result": float(m1182.total - pm.amount),
                   "input_sources": {"invoice": src("26,400.00", 0), "payment": src("13 200,00", 1)}},
      output_format="invoice | payments | balance and due date | schedule/split justified (YES + source / NO DOCUMENT FOUND)",
      anomalies=["A03"])

    # ============================================================== T7 payments before invoice or delivery
    early = []
    for x in sep_pay:
        for num, a in x.settles:
            i = inv(num)
            dn = w.dn(i.dn) if i.dn else None
            if x.date < i.date or (dn and x.date < dn.date):
                po = w.po_of(i)
                justified = bool(po and "deposit" in po.terms)
                early.append((x, i, dn, justified))
    assert [(x.payee, j) for x, i, dn, j in early] == [("RVE", True), ("HAR", False)], early
    (xr, ir, dr, _), (xh, ih, dh, _) = early
    Q(pilot="T7", type="multi_document", style="list", difficulty="hard", topic="ap:chronology",
      failure_modes=["multi_evidence_combination", "deep_in_report"], control="Chronology of payment vs invoice and delivery",
      rule="Flag payments dated before the invoice or before the delivery note/service report; JUSTIFIED only if a signed "
           "PO or contract expressly provides for payment before delivery or invoicing.",
      question="For every supplier payment on the September 2026 bank statement of Azur Marine Services S.A.M. that settles, "
               "fully or partly, a purchase invoice, compare the payment date with (i) the date of that invoice and (ii) the "
               "date of the related delivery note or service report, if any. List only the payments dated before the "
               "invoice date or before the delivery/service date. For each: supplier, payment date and amount, invoice "
               "number and date, delivery note or service report number and date, number of days between payment and "
               "invoice, and JUSTIFIED if a signed purchase order or contract in the file expressly provides for payment "
               "before delivery or invoicing (cite it), otherwise NOT JUSTIFIED. Do not qualify the operation any further.",
      natural="Did we pay any supplier before receiving the goods or the invoice in September 2026?",
      answer=f"Two payments precede the invoice and the delivery. (1) Riviera Electronics SAS: EUR {e(xr.amount)} paid on "
             f"{fdate(xr.date)}; invoice {ir.number} dated {fdate(ir.date)} ({(ir.date - xr.date).days} days later); delivery "
             f"note {dr.number} dated {fdate(dr.date)}. JUSTIFIED: purchase order {po_num['rve_aug']} provides for a 30% "
             f"deposit of the gross amount on order (deducted on the invoice). (2) Harbor Parts B.V.: EUR {e(xh.amount)} "
             f"paid on {fdate(xh.date)} with the reference HP-26-1450; invoice {ih.number} dated {fdate(ih.date)} "
             f"({(ih.date - xh.date).days} days later); delivery note {dh.number} dated {fdate(dh.date)}. NOT JUSTIFIED: "
             f"purchase order {po_num['har_sep']} states 14 days net from invoice date and no document provides for a "
             f"prepayment.",
      key_facts=[kf("Harbor payment date", xh.date), kf("Harbor invoice date", ih.date), kf("Harbor delivery date", dh.date),
                 kf("Harbor not justified", "NOT JUSTIFIED"), kf("Riviera justified", "JUSTIFIED"),
                 kf("Riviera deposit", xr.amount), kf("Harbor days", "8")],
      evidence=ev("bank:2026-09", "HP-26-1450", "ACOMPTE 30%") + ev("inv:HP-26-1450", ("Invoice date", "12-09-2026"))
      + ev("dn:HP-DN-26-0931", ("Date", "11-09-2026")) + ev(f"po:{po_num['har_sep']}", ("Payment terms", "14 days"))
      + ev("inv:RE-2026-0733", ("Date de facture", "17/09/2026")) + ev(f"po:{po_num['rve_aug']}", "30% deposit"),
      calculation=None,
      output_format="table: supplier | payment date/amount | invoice no./date | DN/service report no./date | days | JUSTIFIED/NOT JUSTIFIED",
      anomalies=["A04"])

    # ============================================================== T8 full review of the September journal
    findings, not_found, passes = [], [], 0
    seen_num = set()
    for piece, d, i in sj:
        fails = []
        if not i.in_corpus:
            not_found.append((piece, i))
            continue
        po = w.po_of(i)
        if i.s.po_required and i.kind == "invoice" and not (po and po.date <= i.date):
            fails.append("(2) no PO")
        dn = w.dn(i.dn) if i.dn else None
        if i.kind == "invoice" and po is not None and i.sup != "NTS" and not dn:
            fails.append("(3) no delivery note / service report")
        if dn and i.kind == "invoice":
            for ln in i.lines:
                rec = next((dl for desc, o, dl, u in dn.items if desc == ln.desc), None)
                if rec is not None and ln.qty > rec:
                    fails.append(f"(3) quantity invoiced {ln.qty} > delivered {rec}")
        if i.stated_vat is not None and i.stated_vat != i.vat_correct:
            fails.append("(4) VAT error")
        if (i.sup, i.number) in seen_num:
            fails.append("(5) booked twice")
        seen_num.add((i.sup, i.number))
        if fails:
            findings.append((piece, i, fails))
        else:
            passes += 1
    exp_find = [("AC-2609-010", "NYS-2026-114"), ("AC-2609-011", "F26-02214"), ("AC-2609-016", "QMR 0912"),
                ("AC-2609-017", "SME-26-0457"), ("AC-2609-022", "FA-2026-0917")]
    assert [(p, i.number) for p, i, _ in findings] == exp_find, [(p, i.number, f) for p, i, f in findings]
    assert [(p, i.number) for p, i in not_found] == [("AC-2609-027", "LMP-26-1297")] and passes == 21
    jtot = sum((i.total * i.sign for _, _, i in sj), D(0))
    prh = inv("F26-02214")
    qty_stake = D("4") * D("68.50")
    Q(pilot="T8", type="multi_evidence", style="list", difficulty="hard", topic="ap:full_review",
      failure_modes=["multi_evidence_combination", "deep_in_report", "split_across_pages"],
      control="Complete review of the September purchase journal",
      rule="Checks (1) document found, (2) PO for PO-required suppliers, (3) DN/service report and quantities, (4) VAT "
           "arithmetic, (5) not booked earlier in the journal.",
      question="Review every line of the September 2026 purchase journal (AC) of Azur Marine Services S.A.M. First state how "
               "many lines the journal contains and its total including VAT. Then, for each line, find the invoice document "
               "in the file and apply these checks: (1) the document is in the file; (2) for suppliers marked \"BC requis = "
               "Oui\" in the supplier master file, a purchase order dated on or before the invoice exists; (3) for goods and "
               "on-board works ordered by PO (software licences excluded), a delivery note or service report exists and no "
               "invoiced quantity exceeds the quantity delivered (invoice lines that do not appear on the delivery note, such as delivery, freight or installation labour, are excluded); (4) where the "
               "invoice shows a VAT amount, it equals net amount x VAT rate to the cent; (5) the invoice number does not "
               "already appear on an earlier line of the journal. Report every line failing a check (piece, supplier, "
               "invoice number, failed check, amount at stake), every line whose document you could not find, and the "
               "number of lines that pass all checks. If you cannot complete the review, say exactly which lines were not "
               "reviewed.",
      natural="Can you do a complete control review of the September 2026 purchase journal?",
      answer=f"The September 2026 purchase journal has 27 lines, total EUR {e(jtot)} incl. VAT (the SeaGlass credit note "
             f"counted negative). Lines failing a check: AC-2609-010 Northstar Yacht Services NYS-2026-114 – (2) no purchase "
             f"order, EUR 3,540.00; AC-2609-011 Provence Hydraulique F26-02214 – "
             f"(3) 40 hoses invoiced vs 36 delivered (delivery note BL-PH-26-1187), EUR {e(qty_stake)} net "
             f"(EUR {e(qty_stake * D('1.2'))} incl. VAT); AC-2609-016 Quick Marine Repairs QMR 0912 – (2) no purchase "
             f"order, EUR 1,680.00; AC-2609-017 Sud Marine Électricité SME-26-0457 – (4) VAT shown EUR 1,846.00 instead "
             f"of EUR 1,864.00, EUR 18.00; AC-2609-022 Côte d'Azur Ship Chandlers FA-2026-0917 – (5) already booked as "
             f"AC-2609-007, EUR 2,862.00. Document not found: AC-2609-027 Le Marché du Port LMP-26-1297 "
             f"(EUR 1,884.60). The other 21 lines pass all checks. All 27 lines were reviewed.",
      key_facts=[kf("journal lines", "27"), kf("journal total", jtot), kf("no PO Northstar", "NYS-2026-114"),
                 kf("quantity issue", "F26-02214"), kf("quantity at stake", qty_stake), kf("VAT error", "SME-26-0457"),
                 kf("duplicate", "AC-2609-022"), kf("document not found", "LMP-26-1297"), kf("lines passing", "21"),
                 kf("no PO QMR", "QMR 0912")],
      evidence=ev("journal:9", "TOTAL JOURNAL AC", ("AC-2609-010", "NYS-2026-114"), ("AC-2609-027", "LMP-26-1297"))
      + ev("dn:BL-PH-26-1187", ("FHP-12-2", "Reliquat"), ("Flexible hydraulique", "40"))
      + ev("inv:SME-26-0457", ("TVA 20 %", "1 846,00"), ("Total HT", "9 320,00"))
      + ev("master", ("401NYS", "Oui"), ("401QMR", "Oui")),
      calculation=None,
      output_format="journal line count and total; table of failing lines (piece | supplier | invoice | check | amount); "
                    "documents not found; number of lines passing; coverage statement",
      anomalies=["A01", "A05", "A06", "A09", "A10", "A18"])

    # ============================================================== T9 invoices without PO
    nopo = [(p, i) for p, d, i in sj if i.s.po_required and i.kind == "invoice" and i.total > 1000 and not w.po_of(i)]
    assert [i.number for _, i in nopo] == ["NYS-2026-114", "QMR 0912"]
    pq = next(x for x in sep_pay if x.payee == "QMR")
    pn = next(x for x in sep_pay if x.payee == "NYS")
    Q(pilot="T9", type="multi_document", style="list", difficulty="medium", topic="ap:missing_po",
      failure_modes=["multi_evidence_combination", "header_dependency"], control="Invoices without purchase order",
      rule="PO-required supplier, invoice above EUR 1,000.00 incl. VAT, no PO referenced and none in the file.",
      question="List the invoices booked in the September 2026 purchase journal of Azur Marine Services S.A.M. that (a) come "
               "from a supplier marked \"BC requis = Oui\" (PO required) in the supplier master file, (b) exceed EUR 1,000.00 "
               "including VAT, and (c) do not reference a purchase order and have no purchase order in the file. For each: "
               "supplier, invoice number and date, amount including VAT, whether a delivery note or service report signed on "
               "board exists (YES with its number / NO), and whether the invoice was paid by 30/09/2026 (date and amount). "
               "Do not draw conclusions beyond these facts.",
      natural="Which September 2026 invoices were booked and paid without a purchase order?",
      answer=f"Two invoices. (1) Northstar Yacht Services SARL NYS-2026-114 of 09/09/2026, EUR 3,540.00 incl. VAT; signed "
             f"delivery note or service report: NO (only the Master's e-mail of 06/09/2026 describing the emergency); paid on "
             f"{fdate(pn.date)}, EUR {e(pn.amount)}. (2) Quick Marine Repairs invoice No 0912 (QMR 0912) of 12/09/2026, "
             f"EUR 1,680.00; service report: YES, QMR-SR-0911 of 11/09/2026 signed by the Chief Engineer of M/Y Selene; "
             f"paid on {fdate(pq.date)}, EUR {e(pq.amount)}.",
      key_facts=[kf("Northstar invoice", "NYS-2026-114"), kf("Northstar amount", D("3540.00")),
                 kf("QMR invoice", "0912"), kf("QMR amount", D("1680.00")), kf("QMR service report", "QMR-SR-0911"),
                 kf("Northstar paid date", pn.date), kf("QMR paid date", pq.date)],
      evidence=ev("master", ("401NYS", "Oui"), ("401QMR", "Oui")) + ev("inv:NYS-2026-114", ("Facture n°", "NYS-2026-114"))
      + ev("inv:QMR 0912", "INVOICE No 0912") + ev("dn:QMR-SR-0911", ("No.", "QMR-SR-0911"))
      + ev("bank:2026-09", "NYS-2026-114", "QMR 0912"),
      calculation=None,
      output_format="table: supplier | invoice | date | amount | DN/service report (YES no. / NO) | paid (date, amount)",
      anomalies=["A05", "A06"])

    # ============================================================== T10 beneficiary IBAN vs master file
    transfers = [x for x in sep_pay if x.method == "SEPA"]
    bad = [x for x in transfers if x.payee not in SUPPLIERS or x.iban != SUPPLIERS[x.payee].iban]
    assert [x.payee for x in bad] == ["LME", "DUBOIS", "BLUEWATER"] or sorted(x.payee for x in bad) == ["BLUEWATER", "DUBOIS", "LME"]
    pl = next(x for x in bad if x.payee == "LME")
    Q(pilot="T10", type="multi_document", style="list", difficulty="hard", topic="ap:bank_details",
      failure_modes=["multi_evidence_combination", "similar_table_labels"], control="Beneficiary bank details control",
      rule="MATCH / MISMATCH (supplier in master file, different IBAN) / NOT IN MASTER FILE; call-back required by "
           "PRC-FIN-04 section 6.",
      question="For every SEPA transfer executed in September 2026 (Banque Riviera Monaco payment execution notices "
               "LOT-2609-xx), compare the beneficiary IBAN with the IBAN recorded in the supplier master file of Azur Marine "
               "Services S.A.M. Classify each transfer MATCH, MISMATCH (supplier in the master file, different IBAN) or NOT "
               "IN MASTER FILE (beneficiary absent from the master file). State how many transfers you checked and list "
               "those that are not MATCH with date, beneficiary, amount, IBAN used and IBAN on file. For each MISMATCH, say "
               "which document requested the change and whether the file shows the call-back confirmation required by "
               "policy PRC-FIN-04 (YES/NO).",
      natural="Did we send any September 2026 payment to bank details that differ from the supplier file?",
      answer=f"{len(transfers)} SEPA transfers were checked; {len(transfers) - 3} MATCH. MISMATCH: 18/09/2026, Liguria Marine "
             f"Electronics S.r.l., EUR {e(pl.amount)} (invoice LME-26-0611) sent to {LME_NEW_IBAN} instead of the IBAN on "
             f"file {SUPPLIERS['LME'].iban}. The change was requested by an e-mail of 14/09/2026 from "
             f"amministrazione@lme-sanremo-it.example (Liguria's invoices are issued from amministrazione@lme-sanremo.example) "
             f"and "
             f"accepted by e-mail on 15/09/2026; call-back confirmation: NO. NOT IN MASTER FILE: 25/09/2026, DUBOIS "
             f"JULIEN, EUR 3,750.00, IBAN {OUTSIDE_PAYEES['DUBOIS']['iban']}; "
             f"29/09/2026, BLUEWATER CONSULTING SARL, EUR 1,980.00, IBAN {OUTSIDE_PAYEES['BLUEWATER']['iban']}.",
      key_facts=[kf("transfers checked", str(len(transfers))), kf("mismatch supplier", "Liguria Marine Electronics"),
                 kf("IBAN used", LME_NEW_IBAN, [LME_NEW_IBAN.replace(" ", "")]),
                 kf("mismatch amount", pl.amount), kf("call-back", "NO", ["no call-back"]),
                 kf("not in master 1", "DUBOIS"), kf("not in master 2", "BLUEWATER")],
      evidence=ev(batch_keys[pl.date], "LME-26-0611") + ev("master", "401LME") + ev("mail:lme_bank", "IBAN: LT")
      + ev("mail:lme_reply", "Noted, thank you.") + ev(batch_keys[u1.date], "DUBOIS JULIEN")
      + ev(batch_keys[u2.date], "BLUEWATER CONSULTING SARL"),
      calculation=None,
      output_format="count checked; table: date | beneficiary | amount | IBAN used | IBAN on file | status | change request | call-back",
      anomalies=["A12", "A13", "A14"])

    # ============================================================== T11 breakdown of September debits
    sep_bank = [b for b in w.bank if b.date.month == 9]
    cats = {"supplier": "A", "outside": "B", "payroll": "C", "social": "D", "tax": "E", "fees": "F"}
    agg = {c: [D(0), 0] for c in "ABCDEF"}
    per_sup: dict[str, D] = {}
    for b in sep_bank:
        if b.debit:
            c = cats[b.category]
            agg[c][0] += b.debit
            agg[c][1] += 1
            if c == "A":
                per_sup[b.payment.payee_name] = per_sup.get(b.payment.payee_name, D(0)) + b.debit
    tdeb = sum((b.debit for b in sep_bank), D(0))
    assert tdeb == sum((v[0] for v in agg.values()), D(0)) == D("242173.01")
    A = agg["A"][0]
    sup_lines = "; ".join(f"{k} EUR {e(v)}" for k, v in sorted(per_sup.items()))
    Q(pilot="T11", type="calculation", style="list", difficulty="hard", topic="bank:breakdown",
      failure_modes=["multi_evidence_combination", "similar_table_labels"], control="Reconcilable breakdown of bank debits",
      rule="Categories A-F; A + B + C + D + E + F must equal the statement's total debits.",
      question="Break down all debits on the September 2026 bank statement of Azur Marine Services S.A.M. into: (A) payments "
               "of supplier invoices, including deposits, partial payments and direct debits; (B) transfers with no "
               "invoice, credit note or purchase order in the file; (C) payroll; (D) social contributions; (E) VAT; (F) bank "
               "charges. Give the number of operations and the total of each category, check that the six totals add up to "
               "the total debits shown on the statement, and give category A per supplier.",
      natural="How much did we pay out in September 2026, and to whom?",
      answer=f"Total debits on the September 2026 statement: EUR {e(tdeb)}. (A) supplier invoice payments: "
             f"{agg['A'][1]} operations, EUR {e(A)}; (B) unmatched transfers: {agg['B'][1]} operations, EUR {e(agg['B'][0])}; "
             f"(C) payroll: {agg['C'][1]} operation, EUR {e(agg['C'][0])}; (D) social contributions: {agg['D'][1]} operation, "
             f"EUR {e(agg['D'][0])}; (E) VAT: {agg['E'][1]} operation, EUR {e(agg['E'][0])}; (F) bank charges: "
             f"{agg['F'][1]} operations, EUR {e(agg['F'][0])}. A + B + C + D + E + F = EUR {e(tdeb)}, equal to the "
             f"statement total. Category A by supplier: {sup_lines}.",
      key_facts=[kf("total debits", tdeb), kf("supplier payments", A), kf("unmatched", agg["B"][0]),
                 kf("payroll", agg["C"][0]), kf("social", agg["D"][0]), kf("VAT", agg["E"][0]), kf("bank charges", agg["F"][0]),
                 kf("supplier payment count", str(agg["A"][1]))],
      evidence=ev("bank:2026-09", "TOTAL DES MOUVEMENTS", "SALAIRES", "COTISATIONS SOCIALES", "PAIEMENT TVA",
                  "FRAIS TENUE", "ABONNEMENT BANQUE", "COMMISSIONS VIREMENTS", "MISC REF", "BLUEWATER"),
      calculation=calc_from({"total_debits": tdeb, "misc": u1.amount, "bluewater": u2.amount, "payroll": agg["C"][0],
                             "social": agg["D"][0], "vat": agg["E"][0], "fee_account": D("45.00"),
                             "fee_online": D("18.00"), "fee_transfers": D("12.00")},
                            "total_debits - misc - bluewater - payroll - social - vat - fee_account - fee_online - fee_transfers",
                            A),
      output_format="table: category | count | total; check vs statement total; category A per supplier",
      anomalies=["A13", "A14"], expected_rows=[{"category": k, "count": v[1], "total": str(v[0])} for k, v in agg.items()])

    # ============================================================== T13 cut-off
    mrs = inv("MRS-2026-0298")
    vpn = pos["vpn_sep"]
    accr = m418.net + mrs.net + vpn.net
    assert accr == D("24070.00")
    # ============================================================== T12 exception register
    register = [
        ("DUPLICATE BOOKING", "Côte d'Azur Ship Chandlers SAS", "FA-2026-0917", cas917.total),
        ("SHORT PAYMENT", "SeaGlass Coatings S.r.l.", "SG-2026/0877", diff),
        ("PARTIAL PAYMENT", "Marina Fuel Services S.A.M.", "INV-2026-1182", m1182.total - pm.amount),
        ("PAYMENT BEFORE INVOICE OR DELIVERY NOT JUSTIFIED", "Harbor Parts B.V.", "HP-26-1450", xh.amount),
        ("INVOICE WITHOUT PO", "Northstar Yacht Services SARL", "NYS-2026-114", D("3540.00")),
        ("INVOICE WITHOUT PO", "Quick Marine Repairs", "QMR 0912", D("1680.00")),
        ("PO APPROVAL BELOW REQUIRED LEVEL", "NavTech Systems GmbH", nts.number, nts.net),
        ("PO APPROVAL BELOW REQUIRED LEVEL", "EcoMarine Waste Services SAS", eco.number, eco.net),
        ("QUANTITY INVOICED > DELIVERED", "Provence Hydraulique SARL", "F26-02214", qty_stake),
        ("VAT CALCULATION ERROR", "Sud Marine Électricité SARL", "SME-26-0457", D("18.00")),
        ("NON-COMPLIANT INVOICE", "Quick Marine Repairs", "QMR 0912", D("1680.00")),
        ("BENEFICIARY IBAN DIFFERENT FROM MASTER FILE", "Liguria Marine Electronics S.r.l.", "LME-26-0611", pl.amount),
        ("UNMATCHED BANK DEBIT", "DUBOIS JULIEN", "MISC REF 0925-77", u1.amount),
        ("UNMATCHED BANK DEBIT", "BLUEWATER CONSULTING SARL", "CONSULTING SEPT 2026", u2.amount),
        ("CUT-OFF - TO ACCRUE", "Mediterra Marine Supplies S.A.M.", "INV-2026-0418", m418.net),
        ("CUT-OFF - TO ACCRUE", "Monaco Rigging & Sails S.A.R.L.", "MRS-2026-0298", mrs.net),
        ("CUT-OFF - TO ACCRUE", "Var Pneumatique SAS", "VP-BL-26-0544", vpn.net),
    ]
    counts: dict[str, int] = {}
    for t, *_ in register:
        counts[t] = counts.get(t, 0) + 1
    reg_txt = "; ".join(f"{t} – {s} {n} (EUR {e(a)})" for t, s, n, a in register)
    Q(pilot="T12", type="multi_evidence", style="list", difficulty="hard", topic="ap:exception_register",
      failure_modes=["multi_evidence_combination", "deep_in_report", "multiple_entities"],
      control="Consolidated exception register (every exception carried to the summary)",
      rule="Closed list of 12 exception types with explicit definitions and amounts at stake.",
      question="Prepare the exception register of the September 2026 accounts payable close of Azur Marine Services S.A.M. "
               "Use only these types: DUPLICATE BOOKING (invoice booked twice in the September journal; amount = invoice "
               "incl. VAT); SHORT PAYMENT (payment citing an invoice that leaves less than EUR 100.00 unpaid; amount = "
               "unpaid); PARTIAL PAYMENT (payment citing an invoice that leaves EUR 100.00 or more unpaid; amount = unpaid); "
               "PAYMENT BEFORE INVOICE OR DELIVERY NOT JUSTIFIED (no signed PO or contract provides for it; amount = "
               "payment); INVOICE WITHOUT PO (supplier with PO required, no PO; amount = invoice incl. VAT); PO APPROVAL "
               "BELOW REQUIRED LEVEL (policy PRC-FIN-04; amount = PO net); QUANTITY INVOICED > DELIVERED (amount = excess "
               "quantity x net unit price); VAT CALCULATION ERROR (amount = VAT difference); NON-COMPLIANT INVOICE "
               "(mandatory mention missing; amount = invoice incl. VAT); BENEFICIARY IBAN DIFFERENT FROM MASTER FILE "
               "(amount = payment); UNMATCHED BANK DEBIT (amount = debit); CUT-OFF - TO ACCRUE (September goods or services "
               "not in the September journal; amount = net). Scope: September 2026 journal, September bank statement, "
               "September purchase orders and September deliveries. A contractual deposit is not an exception. One row per "
               "exception: type, supplier or beneficiary, document number, amount at stake, source document. Then give the "
               "count per type and the total count.",
      natural="Give me the full list of accounts payable exceptions for the September 2026 close.",
      answer=f"17 exceptions. {reg_txt}. Count per type: " + ", ".join(f"{t} {c}" for t, c in counts.items())
             + ". The Riviera Electronics deposit of 02/09/2026 is contractual and is not an exception.",
      key_facts=[kf("total exceptions", "17"), kf("duplicate", "FA-2026-0917"), kf("short payment", "SG-2026/0877"),
                 kf("partial payment", "INV-2026-1182"), kf("unjustified early payment", "HP-26-1450"),
                 kf("IBAN", "LME-26-0611"), kf("VAT error", "SME-26-0457"), kf("quantity", "F26-02214"),
                 kf("cut-off Mediterra", "INV-2026-0418"), kf("cut-off rigging", "MRS-2026-0298"),
                 kf("cut-off Var Pneumatique", "VP-BL-26-0544"), kf("approval NavTech", nts.number),
                 kf("approval EcoMarine", eco.number), kf("unmatched MISC", "0925-77"), kf("unmatched Bluewater", "BLUEWATER")],
      evidence=ev("journal:9", ("AC-2609-022", "FA-2026-0917")) + ev("bank:2026-09", "SG-2026/0877 LESS CN0112", "INV 1182",
                                                                      "HP-26-1450", "MISC REF", "BLUEWATER")
      + ev("inv:SME-26-0457", ("TVA 20 %", "1 846,00")) + ev("dn:BL-PH-26-1187", ("FHP-12-2", "Reliquat"))
      + ev(batch_keys[pl.date], "LME-26-0611") + ev("inv:INV-2026-0418", "RECEIVED 02/10/2026")
      + ev("inv:MRS-2026-0298", "RECEIVED 06 OCT 2026") + ev("dn:VP-BL-26-0544", "VP-BL-26-0544")
      + ev(f"po:{nts.number}", "Approved by") + ev(f"po:{eco.number}", "Approved by"),
      calculation=None,
      output_format="table: type | supplier/beneficiary | document | amount at stake | source; counts per type; total count",
      anomalies=[f"A{n:02d}" for n in range(1, 18)],
      expected_rows=[{"type": t, "party": s, "document": n, "amount": str(a)} for t, s, n, a in register])

    Q(pilot="T13", type="multi_document", style="list", difficulty="medium", topic="ap:cut_off",
      failure_modes=["multi_evidence_combination", "terminology_mismatch"], control="Period-end cut-off (accruals)",
      rule="Invoices received after 30/09 for goods/services delivered by 30/09, and goods/services received without "
           "invoice, are accrued at net amount (invoice net, else PO price).",
      question="Apply the September 2026 cut-off rules of Azur Marine Services S.A.M.: supplier invoices received after "
               "30/09/2026 for goods or services delivered or completed by 30/09/2026, and goods or services received by "
               "30/09/2026 without any invoice, are accrued at their net amount (the invoice net amount if an invoice exists, "
               "otherwise the PO price). Exclude anything already booked in the September purchase journal. List every item "
               "to accrue with supplier, document(s), delivery or completion date, invoice date and receipt date where "
               "applicable, and net amount; give the total to accrue at 30/09/2026.",
      natural="What purchases do we need to accrue at 30 September 2026?",
      answer=f"Three items, total EUR {e(accr)} net. (1) Mediterra Marine Supplies S.A.M., invoice INV-2026-0418: goods "
             f"delivered 25/09/2026 (MMS-DN-26-0925), invoice dated 30/09/2026, received 02/10/2026 – EUR {e(m418.net)}. "
             f"(2) Monaco Rigging & Sails S.A.R.L., invoice MRS-2026-0298: works completed 24/09/2026 (service report "
             f"MRS-SR-26-0924), invoice dated 29/09/2026, received 06/10/2026 – EUR {e(mrs.net)}. (3) Var Pneumatique SAS: "
             f"2 compressors received 28/09/2026 (delivery note VP-BL-26-0544), no invoice in the file – accrued at the "
             f"price of purchase order {vpn.number}, 2 x EUR 1,960.00 = EUR {e(vpn.net)}.",
      key_facts=[kf("total accrual", accr), kf("Mediterra net", m418.net), kf("rigging net", mrs.net),
                 kf("Var Pneumatique PO price", vpn.net), kf("Var Pneumatique delivery note", "VP-BL-26-0544")],
      evidence=ev("inv:INV-2026-0418", "RECEIVED 02/10/2026", ("Net total", "12,800.00"))
      + ev("inv:MRS-2026-0298", "RECEIVED 06 OCT 2026", ("Net total", "7,350.00"))
      + ev("dn:VP-BL-26-0544", ("Date", "28/09/2026")) + ev(f"po:{vpn.number}", ("TOTAL NET AMOUNT", "3,920.00")),
      calculation={"inputs": {"mediterra": float(m418.net), "rigging": float(mrs.net), "var_pneumatique": float(vpn.net)},
                   "operation": "mediterra + rigging + var_pneumatique", "result": float(accr),
                   "input_sources": {"mediterra": src("12,800.00", 0), "rigging": src("7,350.00", 1),
                                     "var_pneumatique": src("3,920.00", 3)}},
      output_format="table: supplier | documents | delivery/completion date | invoice date | received | net to accrue; total",
      anomalies=["A15", "A16", "A17"])

    # ============================================================== T14 VAT arithmetic and mandatory mentions
    sme = inv("SME-26-0457")
    assert sme.vat_correct - sme.vat == D("18.00")
    Q(pilot="T14", type="multi_document", style="list", difficulty="medium", topic="tax:vat_invoice_compliance",
      failure_modes=["header_dependency", "terminology_mismatch"], control="VAT arithmetic and mandatory invoice mentions",
      rule="VAT = base x rate rounded to the cent and total = net + VAT; checklist of mandatory mentions.",
      question="Check the purchase invoices booked in the September 2026 purchase journal of Azur Marine Services S.A.M. on two "
               "points: (1) VAT arithmetic: for each VAT rate shown, VAT amount = taxable base x rate rounded to the cent, "
               "and total = net + VAT; (2) mandatory mentions: supplier name and address, supplier VAT number, customer name "
               "and address, invoice number, invoice date, description and quantity, net amount, VAT rate and VAT amount (or "
               "a reverse-charge or exemption mention), total amount, due date or payment terms. List each invoice failing a "
               "check with the amounts shown, the correct amounts and the difference, or the missing mentions. Invoices "
               "whose document is not in the file are out of scope; credit notes need no due date.",
      natural="Are there VAT errors or non-compliant supplier invoices in September 2026?",
      answer=f"Two invoices fail. (1) Sud Marine Électricité SARL SME-26-0457: net EUR 9,320.00, VAT shown EUR 1,846.00 "
             f"instead of EUR 1,864.00 (9,320.00 x 20%), difference EUR 18.00; total shown EUR 11,166.00 instead of "
             f"EUR 11,184.00. (2) Quick Marine Repairs invoice No 0912: missing supplier address, supplier VAT number, "
             f"customer address, quantity, net amount, VAT rate and VAT amount (only a total of EUR 1,680.00 is shown) and "
             f"due date or payment terms. All other invoices in the file pass both checks.",
      key_facts=[kf("VAT error invoice", "SME-26-0457"), kf("VAT shown", D("1846.00")), kf("VAT correct", D("1864.00")),
                 kf("VAT difference", D("18.00")), kf("correct total", D("11184.00")),
                 kf("non-compliant invoice", "0912"), kf("missing supplier VAT number", "supplier VAT number")],
      evidence=ev("inv:SME-26-0457", ("Total HT", "9 320,00"), ("TVA 20 %", "1 846,00"), ("Total TTC", "11 166,00"))
      + ev("inv:QMR 0912", "INVOICE No 0912", "To: Azur Marine Services", ("TOTAL", "1,680.00 EUR")),
      calculation={"inputs": {"net": float(sme.net), "rate": 0.2, "vat_shown": float(sme.vat)},
                   "operation": "net * rate - vat_shown", "result": float(sme.vat_correct - sme.vat),
                   "input_sources": {"net": src("9 320,00", 0), "rate": {"evidence_index": 0, "raw": "20 %", "unit": "%",
                                                                         "scale": 0.01},
                                     "vat_shown": src("1 846,00", 0)}},
      output_format="table: invoice | check | shown | correct | difference / missing mentions",
      anomalies=["A10", "A11"])

    # ============================================================== T15 store isolation (negative)
    Q(pilot="T15", type="negative", style="lookup", difficulty="medium", topic="security:store_isolation",
      failure_modes=["multiple_entities"], control="Store isolation probe (technical test, see README)",
      rule="The probe document isolation_probe/probe_doc_001.pdf is ingested ONLY in a different store. Any answer "
           "giving its amount (48,620.55) or aircraft (F-HELI) from the Azur store is a leak.",
      question="What is the total amount of invoice KAF-2026-7731 issued by Kestrel Aviation Fuels Ltd, and which aircraft "
               "was refuelled?",
      natural="How much was Kestrel Aviation Fuels invoice KAF-2026-7731?",
      answer="This cannot be established from the documents of Azur Marine Services S.A.M.: no document from Kestrel "
             "Aviation Fuels Ltd and no invoice KAF-2026-7731 is in this corpus.",
      key_facts=[], evidence=[], calculation=None, answerable=False,
      output_format="abstention; the answer must not contain 48,620.55 or F-HELI", anomalies=[])

    # ---------------------------------------------------------------- write
    ANOMALIES.extend(anomaly_register(w, po_num))
    order = ["B1", "B2", "B3", "B4", "B5"] + [f"T{n}" for n in range(1, 16)]
    QUESTIONS.sort(key=lambda q: order.index(q["pilot"]))
    out_rows = []
    for n, q in enumerate(QUESTIONS, 1):
        multi = len({x["document_id"] for x in q["evidence"]}) > 1
        meta = {"type": q["type"], "difficulty": q["difficulty"], "requires_calculation": q.get("calculation") is not None,
                "requires_multiple_documents": multi, "answerable": q.get("answerable", True), "tier": "silver",
                "style": q["style"], "topic": q["topic"], "failure_modes": q["failure_modes"], "pilot_id": q["pilot"],
                "control": q["control"], "control_rule": q["rule"], "output_format": q["output_format"],
                "anomalies_tested": q["anomalies"]}
        if q.get("expected_rows"):
            meta["expected_rows"] = q["expected_rows"]
        if q["type"] == "multi_document" and not multi:
            meta["type"] = "multi_evidence" if len(q["evidence"]) > 1 else "table"
        out_rows.append({"id": f"acc_q_{n:03d}", "question": q["question"], "question_natural": q["natural"],
                         "reference_answer": q["answer"], "key_facts": q["key_facts"], "evidence": q["evidence"],
                         "metadata": meta, "calculation": q.get("calculation")})
    ds = ROOT / "datasets"
    ds.mkdir(exist_ok=True)
    (ds / "accountingbench_v1.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), "utf-8")
    files = {d["document_id"]: d["filename"] for d in MANIFEST["documents"]}
    simple = [{"id": r["id"], "pilot_id": r["metadata"]["pilot_id"], "question": r["question"],
               "question_natural": r["question_natural"], "answer": r["reference_answer"],
               "documents": list(dict.fromkeys(files[x["document_id"]] for x in r["evidence"])),
               "pages": [f"{files[x['document_id']]}:{x['page']}" for x in r["evidence"]],
               "answerable": r["metadata"]["answerable"]} for r in out_rows]
    (ds / "accountingbench_v1_simple.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in simple), "utf-8")
    with open(ds / "accountingbench_v1_simple.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(simple[0]))
        wr.writeheader()
        for r in simple:
            wr.writerow(r | {"documents": "|".join(r["documents"]), "pages": "|".join(r["pages"])})
    qmap: dict[str, list[str]] = {}
    for r in out_rows:
        for a in r["metadata"]["anomalies_tested"]:
            qmap.setdefault(a, []).append(r["id"])
    for a in ANOMALIES:
        a["tested_by"] = qmap.get(a["id"], [])
    (ds / "anomaly_register.json").write_text(json.dumps({"note": "Ground truth - never ingest.", "anomalies": ANOMALIES},
                                                         indent=2, ensure_ascii=False), "utf-8")
    print(f"{len(out_rows)} questions, {len(ANOMALIES)} anomalies -> {ds}")
    return 0


def anomaly_register(w, po_num) -> list[dict]:
    def docs(*keys):
        return [{"key": k, "document_id": did(k)} for k in keys]
    A = [
        ("A01", "duplicate booking", "CAS", "FA-2026-0917 booked twice (AC-2609-007, AC-2609-022) after a DUPLICATA copy",
         "2862.00", ["inv:FA-2026-0917", "inv:FA-2026-0917:duplicata", "journal:9", "mail:cas_dup"]),
        ("A02", "short payment after credit note", "SEA", "7,840.00 due, 7,830.00 paid: 10.00 open", "10.00",
         ["inv:SG-2026/0877", "inv:SG-CN-2026/0112", "bank:2026-09", "ledger:9"]),
        ("A03", "partial payment", "MFS", "INV-2026-1182 26,400.00, paid 13,200.00, no schedule", "13200.00",
         ["inv:INV-2026-1182", "bank:2026-09", "mail:marina"]),
        ("A04", "payment before invoice and delivery, not justified", "HAR", "paid 04/09, DN 11/09, invoice 12/09",
         "4870.00", ["bank:2026-09", "inv:HP-26-1450", "dn:HP-DN-26-0931", f"po:{po_num['har_sep']}"]),
        ("A05", "invoice without PO and without delivery evidence", "NYS", "emergency work authorised verbally", "3540.00",
         ["inv:NYS-2026-114", "mail:captain"]),
        ("A06", "invoice without PO", "QMR", "emergency dive, service report exists", "1680.00",
         ["inv:QMR 0912", "dn:QMR-SR-0911"]),
        ("A07", "PO approved below required level", "NTS", "24,500.00 net approved by Finance Director (CEO required)",
         "24500.00", [f"po:{po_num['nts_sep']}", "policy:procurement"]),
        ("A08", "PO approved below required level", "ECO", "5,640.00 net approved by Operations Manager (FD required)",
         "5640.00", [f"po:{po_num['eco_sep']}", "policy:procurement"]),
        ("A09", "quantity invoiced > delivered", "PRH", "40 hoses invoiced, 36 delivered", "274.00",
         ["inv:F26-02214", "dn:BL-PH-26-1187", "mail:prh"]),
        ("A10", "VAT calculation error", "SME", "VAT 1,846.00 shown instead of 1,864.00", "18.00", ["inv:SME-26-0457"]),
        ("A11", "non-compliant invoice", "QMR", "no supplier address, VAT number, customer address, quantity, net amount, VAT rate and amount, due date",
         "1680.00", ["inv:QMR 0912"]),
        ("A12", "beneficiary IBAN changed by look-alike e-mail, no call-back", "LME", "paid to LT IBAN", "5480.00",
         ["mail:lme_bank", "mail:lme_reply", "master"]),
        ("A13", "unmatched bank debit", "DUBOIS", "VIR SEPA EMIS MISC REF 0925-77", "3750.00", ["bank:2026-09"]),
        ("A14", "unmatched bank debit", "BLUEWATER", "payee not in master file", "1980.00", ["bank:2026-09"]),
        ("A15", "cut-off: invoice received after closing", "MED", "INV-2026-0418 dated 30/09, received 02/10", "12800.00",
         ["inv:INV-2026-0418", "stmt:MED", "mail:med_0418", "dn:MMS-DN-26-0925"]),
        ("A16", "cut-off: invoice received after closing", "MRS", "works 24/09, invoice 29/09 received 06/10", "7350.00",
         ["inv:MRS-2026-0298", "dn:MRS-SR-26-0924", "mail:mrs_0298"]),
        ("A17", "cut-off: goods received not invoiced", "VPN", "DN 28/09, no invoice; PO price", "3920.00",
         ["dn:VP-BL-26-0544", f"po:{po_num['vpn_sep']}", "mail:vpn"]),
        ("A18", "journal line without document in the file", "LMP", "LMP-26-1297 booked (AC-2609-027), PDF missing",
         "1884.60", ["journal:9"]),
    ]
    out = []
    for aid, t, sup, desc, amt, keys in A:
        out.append({"id": aid, "type": t, "party": SUPPLIERS[sup].name if sup in SUPPLIERS else sup, "description": desc,
                    "amount_at_stake": amt, "documents": docs(*keys)})
    # decoys: look like anomalies but are not (must NOT be flagged)
    out.append({"id": "D01", "type": "decoy: contractual deposit (not an exception)", "party": SUPPLIERS["RVE"].name,
                "description": "5,112.00 paid on 02/09 before invoice 17/09; PO provides for a 30% deposit",
                "amount_at_stake": "0.00", "documents": docs("bank:2026-09", f"po:{po_num['rve_aug']}", "inv:RE-2026-0733")})
    out.append({"id": "D02", "type": "decoy: recurring identical amounts (not duplicates)", "party": SUPPLIERS["MBM"].name,
                "description": "berth fees of identical amounts every month, different numbers and dates",
                "amount_at_stake": "0.00", "documents": docs("journal:9")})
    out.append({"id": "D03", "type": "decoy: invoice addressed to the sister company", "party": SUPPLIERS["CAS"].name,
                "description": "FA-2026-0931 to Azur Marine Charter SARL, correctly not booked", "amount_at_stake": "0.00",
                "documents": docs("inv:FA-2026-0931")})
    return out


if __name__ == "__main__":
    sys.exit(main())
