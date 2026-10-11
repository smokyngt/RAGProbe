#!/usr/bin/env python3
"""Generate the AccountingBench corpus (PDFs, manifest, OCR reference text) from world.py.

    python accountingbench/tools/generate_corpus.py            # -> corpus/documents/acc_doc_NNN.pdf + manifest.json

Deterministic: same code, same corpus (fixed seeds, invariant PDFs). Scanned documents are rasterised (image-only
PDF, no text layer); their reference text, used only to check evidence quotes, is kept in corpus/ocr_reference/.
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
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageFilter  # noqa: E402

import fill as FILL  # noqa: E402
import longdocs as LD  # noqa: E402
import render as R  # noqa: E402
from common import D, ROOT, date, fdate, fmt, prev_business_day as R_prev  # noqa: E402
from world import (BANK, EMAILS, ENTITIES, LME_NEW_BIC, LME_NEW_IBAN, PEOPLE, SUPPLIERS, Invoice, L,  # noqa: E402
                   Supplier, build_world, journal, ledger_entries, open_items)

CORPUS = ROOT / "corpus"
DOCS = CORPUS / "documents"
OCR = CORPUS / "ocr_reference"
PROBE = ROOT / "isolation_probe"
# signed delivery notes / service reports that reach accounts payable as scans
SCANNED_DN_SUPPLIERS = {"CAS", "PRH", "SME", "ECO", "MRS", "SEA", "MFS"}
# suppliers that print their general terms of sale overleaf (2-page invoices)
TERMS_SUPPLIERS = {"MED", "MFS", "OSE", "NTS", "NYS", "CAS", "PRH", "RVE", "SME", "ECO", "VPN", "SEA", "LME", "HAR", "MRS", "CRW"}
# unrelated one-page documents removed to keep the corpus at 200 files
DROPPED_NOISE = {"travel", "stcw", "expo", "port_notice", "drill", "assets", "fees", "expenses", "rotation", "charter"}


# chapters that start on a new page, as in the real documents
BREAKS = {
    "annual_accounts": ("Bilan actif", "Bilan passif", "Compte de résultat", "Tableau des immobilisations", "Note 1", "Note 4",
                        "Note 6", "Rapport de gestion"),
    "internal_audit": ("2. Scope", "3. Summary", "4. F1", "4. F3", "4. F5", "4. F7", "5. Rating", "Annex 1", "Annex 2", "Annex 3"),
    "survey": ("Hull", "Inspection – Main deck", "Inspection – Guest", "Inspection – Engine", "Recommendations"),
    "insurance": ("Policy wording", "Schedule of equipment", "Claims history"),
    "lease": ("Article 1", "Annexe"),
    "mgmt_aug": ("Income statement", "Balance sheet", "Budget"),
    "audit": ("Calendrier", "Honoraires"),
    "pricelist": ("Lubricants", "Safety"),
    "loan": ("Échéancier",),
}
POLICY_BREAKS = ("3. Approval", "6. Payments", "Annex A", "Annex C", "Annex D", "Annex E", "Annex F", "Annex G", "Annex I")


PUBLIC_ANNEXES = {
    "policy:procurement": ("eu_vat_invoicing_notes.pdf", "Annex K – Reference: EU VAT invoicing rules",
                           "Explanatory notes on the VAT invoicing rules (Council Directive 2010/45/EU), published by the "
                           "European Commission (DG TAXUD). Reproduced for reference with acknowledgement of the source; "
                           "the authentic texts are those published in the Official Journal of the European Union.",
                           "https://taxation-customs.ec.europa.eu/system/files/2016-09/explanatory_notes_en.pdf"),
}


def with_public_annex(draw, key):
    """Render a document, then append a separator page and a public reference PDF as its last annex."""
    from pypdf import PdfReader, PdfWriter
    fname, title, note, url = PUBLIC_ANNEXES[key]

    def run(path):
        with tempfile.TemporaryDirectory() as td:
            main_pdf, sep_pdf = Path(td) / "main.pdf", Path(td) / "sep.pdf"
            draw(main_pdf)
            R.render_text_doc(sep_pdf, title, "Azur Marine Services S.A.M. – Finance", [("Source", [note, f"Source: {url}"])],
                              date(15, 1), ref="PRC-FIN-04 v3")
            out = PdfWriter()
            for f in (main_pdf, sep_pdf, Path(__file__).parent / "public_sources" / fname):
                for page in PdfReader(str(f)).pages:
                    out.add_page(page)
            with open(path, "wb") as fh:
                out.write(fh)
    return run


def invoice_annex(i, w=None):
    """Annex pages printed by suppliers: packing list, timesheet, bunker detail, licences, call detail, IT report."""
    base = _base_annex(i)
    detail = FILL.invoice_annex_for(i, w) if w is not None and i.sup in TERMS_SUPPLIERS else None
    return (detail or []) + (base or []) or None


def _base_annex(i):
    if i.sup == "RTL":
        return LD.telecom_detail(i.date.month)
    if i.sup == "KIT" and i.date.month >= 7:
        return LD.it_activity(i.date.month)
    if i.sup == "LIB":
        return LD.premium_schedule(i.number)
    return None


@dataclass
class Spec:
    key: str
    doc_type: str
    title: str
    issuer: str
    addressee: str
    doc_date: dt.date
    lang: str
    draw: object  # callable(path)
    scanned: bool = False
    tags: list = field(default_factory=list)
    ext: str = "pdf"
    meta: dict = field(default_factory=dict)


def ts(d: dt.date, h: int, m: int) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, h, m)


def build_specs():
    w = build_world()
    E = ENTITIES
    specs: list[Spec] = []

    def add(key, doc_type, title, issuer, addressee, d, lang, draw, scanned=False, ext="pdf"):
        specs.append(Spec(key, doc_type, title, issuer, addressee, d, lang, draw, scanned, ext=ext))

    # ---------------- invoices and credit notes
    for i in w.invoices:
        if not i.in_corpus:
            continue
        kind = "credit_note" if i.kind == "credit_note" else "supplier_invoice"
        add(f"inv:{i.number}", kind, f"{'Credit note' if kind == 'credit_note' else 'Invoice'} {i.number}", i.s.name,
            E[i.customer]["name"], i.date, i.s.lang, lambda p, i=i: R.render_invoice(p, i, E, w, terms_page=i.sup in TERMS_SUPPLIERS, annex=invoice_annex(i, w)),
            scanned=i.scanned)
    dup = next(i for i in w.invoices if i.number == "FA-2026-0917")
    dup_copy = Invoice(**{**dup.__dict__, "copy_mark": "DUPLICATA", "booked": [], "scanned": True,
                          "notes": dup.notes + ["Duplicata adressé le 21/09/2026 à la demande du client."]})
    add("inv:FA-2026-0917:duplicata", "supplier_invoice", "Invoice FA-2026-0917 (duplicate copy)", dup.s.name,
        E["AMS"]["name"], date(21, 9), "fr", lambda p: R.render_invoice(p, dup_copy, E, w, terms_page=True), scanned=True)

    # invoices addressed to the sister company and older invoices (same suppliers, out of scope)
    extra = [
        Invoice("INV-2026-1190", "MFS", date(18, 9), [L("Marine gasoil (MGO) DMA, delivered by truck, Port Vauban", 4800, "L", "2.000")],
                customer="AMC", vessel="BLUE"),
        Invoice("RE-2026-0741", "RVE", date(22, 9), [L("Contrôle annuel du système de vidéosurveillance", 1, "forfait", "690.00")],
                customer="AMC"),
        Invoice("SME-26-0462", "SME", date(19, 9), [L("Dépannage alternateur 24 V", 1, "forfait", "1180.00"),
                                                    L("Main-d'œuvre électricien", 5, "h", "75.00")], customer="AMC"),
        Invoice("INV-2025-1987", "MED", date(12, 12, 2025), [L("Lube oil SAE 15W-40, 208 L drum", 5, "drum", "728.00", sku="LO-1540-208"),
                                                             L("Delivery and handling", 1, "lot", "300.00", sku="SRV-DEL")],
                vessel="AURELIA"),
        Invoice("FA-2025-1460", "CAS", date(14, 11, 2025), [L("Défenses cylindriques F6", 8, "u", "139.00"),
                                                           L("Livraison quai", 1, "forfait", "250.00")], vessel="SELENE"),
        Invoice("HP-25-0988", "HAR", date(20, 10, 2025), [L("Shaft seal kit, 63 mm, dripless", 1, "kit", "1095.00", "0", sku="HP-SS63"),
                                                         L("Freight DAP Monaco", 1, "lot", "120.00", "0", sku="FRT")], vessel="SELENE"),
        Invoice("SG-2025/1310", "SEA", date(3, 11, 2025), [L("Antifouling Pro-X self-polishing, blue, 2.5 L tin", 20, "tin", "149.00", "0", sku="PX-B-25")],
                vessel="BLUE"),
    ]
    for i in extra:
        add(f"inv:{i.number}", "supplier_invoice", f"Invoice {i.number}", i.s.name, E[i.customer]["name"], i.date,
            i.s.lang, lambda p, i=i: R.render_invoice(p, i, E, w, terms_page=i.sup in TERMS_SUPPLIERS))

    # ---------------- purchase orders and delivery notes / service reports
    for po in w.pos.values():
        add(f"po:{po.number}", "purchase_order", f"Purchase order {po.number}", E["AMS"]["name"], SUPPLIERS[po.sup].name,
            po.date, "en", lambda p, po=po: R.render_po(p, po, SUPPLIERS[po.sup], E, w))
    for dn in w.dns:
        t = "service_report" if dn.kind == "service" else "delivery_note"
        add(f"dn:{dn.number}", t, f"{'Service report' if dn.kind == 'service' else 'Delivery note'} {dn.number}",
            SUPPLIERS[dn.sup].name, E["AMS"]["name"], dn.date, SUPPLIERS[dn.sup].lang,
            lambda p, dn=dn: R.render_dn(p, dn, SUPPLIERS[dn.sup], E, w),
            scanned=dn.scanned or dn.sup in SCANNED_DN_SUPPLIERS)

    # ---------------- quotes and pro-formas (no accounting entry)
    ose_lines = w.pos["ose_aug"].lines
    add("quote:OSE-Q-2026-118", "quote", "Quotation OSE-Q-2026-118", SUPPLIERS["OSE"].name, E["AMS"]["name"], date(12, 8), "en",
        lambda p: R.render_quote(p, "quote", "OSE-Q-2026-118", date(12, 8), SUPPLIERS["OSE"], ose_lines, E, spec=[
            ("Technical specification", ["Liferaft: 12-person SOLAS A-pack, throw-over, container GRP, hydrostatic release "
             "included, service exchange against the unit on board (serial to be confirmed).", "EPIRB: battery and HRU "
             "replacement for 406 MHz units, programming check and registration update.", "Lifejackets: SOLAS/MED 150N "
             "with light and whistle, adult size.", "Extinguishers: 6 kg foam, MED wheel-marked, with bracket."]),
            ("Delivery", "Within 2 weeks of the purchase order, DAP Monaco, Quai Antoine Ier; delivery note signed on board.")]))
    add("pf:OSE-PF-2026-044", "proforma", "Pro-forma invoice OSE-PF-2026-044", SUPPLIERS["OSE"].name, E["AMS"]["name"],
        date(20, 8), "en", lambda p: R.render_quote(p, "proforma", "OSE-PF-2026-044", date(20, 8), SUPPLIERS["OSE"], ose_lines, E))
    add("quote:DEV-RE-2026-0457", "quote", "Quotation DEV-RE-2026-0457", SUPPLIERS["RVE"].name, E["AMS"]["name"], date(18, 8),
        "fr", lambda p: R.render_quote(p, "quote", "DEV-RE-2026-0457", date(18, 8), SUPPLIERS["RVE"], w.pos["rve_aug"].lines, E,
                                       note="Conditions : acompte de 30 % du montant TTC à la commande, solde à 30 jours "
                                            "date de facture.", terms=False))
    competitor = Supplier(**{**SUPPLIERS["RVE"].__dict__, "code": "CSS", "name": "Côte Sécurité Systèmes SAS",
                             "street": "5 Avenue Saint-Roch", "city": "06300 Nice", "vat_id": "FR 58 834 220 117",
                             "reg": "RCS Nice 834 220 117", "color": "#455A64", "logo": "shield",
                             "email": "devis@cote-securite.example"})
    add("quote:CSS-2026-221", "quote", "Quotation CSS-2026-221", competitor.name, E["AMS"]["name"], date(14, 8), "fr",
        lambda p: R.render_quote(p, "quote", "CSS-2026-221", date(14, 8), competitor,
                                 [L("Système de vidéosurveillance IP – kit 8 caméras", 1, "kit", "7450.00", sku="VS-8"),
                                  L("Enregistreur NVR 16 voies 8 To", 1, "u", "2390.00", sku="NVR-16"),
                                  L("Installation (forfait)", 1, "forfait", "4100.00", sku="INST")], E,
                                 note="Offre non retenue.", terms=False))
    add("quote:NTS-Q-2026-0219", "quote", "Quotation NTS-Q-2026-0219", SUPPLIERS["NTS"].name, E["AMS"]["name"], date(2, 9), "en",
        lambda p: R.render_quote(p, "quote", "NTS-Q-2026-0219", date(2, 9), SUPPLIERS["NTS"], w.pos["nts_sep"].lines, E, spec=[
            ("Scope of maintenance", ["Software updates and security patches for the ECDIS workstations of M/Y Aurelia, "
             "M/Y Selene and S/Y Blue Horizon.", "24/7 remote support, annual on-board health check, type-approval "
             "documentation for flag and class."]),
            ("Chart data", "Global coverage of official electronic navigational charts, weekly updates, licences "
             "transferable between the three vessels."),
            ("Service period", "01/10/2026 to 30/09/2027. Invoicing at the start of the period, payment 30 days net.")]))

    # ---------------- supplier statements of account
    def history(prefix, first_no, start, amounts_seed, lang, extra=()):
        """Jan-May 2026 invoices (4 a month) and their payments, all settled: the statement's earlier pages."""
        rnd = random.Random(amounts_seed)
        rows, no = list(extra), first_no
        for m in range(1, 6):  # January-May: all settled before July
            for day in (4, 11, 18, 25):
                d = dt.date(2026, m, day)
                amt = D(rnd.randrange(90000, 980000)) / 100
                rows.append((d, f"{prefix}{no:04d}", "Facture" if lang == "fr" else "Invoice", amt, D(0)))
                pd_ = R_prev(d + dt.timedelta(days=30))
                rows.append((pd_, f"{'VIR' if lang == 'fr' else 'PMT'} {pd_:%d%m%y}",
                             "Règlement reçu" if lang == "fr" else "Payment received – thank you", D(0), amt))
                no += rnd.randrange(7, 13)
        assert no < start, (prefix, no)
        return sorted(rows, key=lambda r: (r[0], r[3] == 0))

    med = SUPPLIERS["MED"]
    med_hist = history("INV-2026-", 21, 312, 7, "en", [
        (date(12, 12, 2025), "INV-2025-1987", "Invoice", D("4728.00"), D(0)),
        (date(9, 1), "PMT 090126", "Payment received – thank you", D(0), D("4728.00"))])
    cas_hist = history("FA-2026-", 102, 788, 11, "fr", [
        (date(14, 11, 2025), "FA-2025-1460", "Facture", D("1634.40"), D(0)),
        (date(12, 12, 2025), "VIR 121225", "Règlement reçu", D(0), D("1634.40"))])
    add("stmt:MED", "supplier_statement", "Statement of account Mediterra Marine Supplies 30/09/2026", med.name, E["AMS"]["name"],
        date(30, 9), "en", lambda p: R.render_supplier_statement(p, med, E, med_hist + [
            (date(14, 7), "INV-2026-0312", "Invoice", D("4869.60"), D(0)),
            (date(13, 8), "PMT 130826", "Payment received – thank you", D(0), D("4869.60")),
            (date(28, 8), "INV-2026-0371", "Invoice", D("11580.00"), D(0)),
            (date(10, 9), "PMT 100926", "Payment received (instalment 1/2)", D(0), D("5790.00")),
            (date(24, 9), "PMT 240926", "Payment received (instalment 2/2)", D(0), D("5790.00")),
            (date(30, 9), "INV-2026-0418", "Invoice – September consumables", D("15360.00"), D(0))],
            date(30, 9), D("15360.00"), note="Please contact billing@mediterra-marine.example for any query on this statement."))
    ose = SUPPLIERS["OSE"]
    add("stmt:OSE", "supplier_statement", "Statement of account Oceanic Safety Europe 30/09/2026", ose.name, E["AMS"]["name"],
        date(30, 9), "en", lambda p: R.render_supplier_statement(p, ose, E, [
            (date(12, 9), "INV-2026-552", "Invoice – safety equipment annual replenishment", D("6200.00"), D(0))],
            date(30, 9), D("6200.00")))
    cas = SUPPLIERS["CAS"]
    add("stmt:CAS", "supplier_statement", "Relevé de compte Côte d'Azur Ship Chandlers 30/09/2026", cas.name, E["AMS"]["name"],
        date(30, 9), "fr", lambda p: R.render_supplier_statement(p, cas, E, cas_hist + [
            (date(7, 7), "FA-2026-0788", "Facture", D("1944.00"), D(0)),
            (date(6, 8), "VIR 060826", "Règlement reçu", D(0), D("1944.00")),
            (date(6, 8), "FA-2026-0851", "Facture", D("2280.00"), D(0)),
            (date(4, 9), "VIR 040926", "Règlement reçu", D(0), D("2280.00")),
            (date(3, 9), "FA-2026-0917", "Facture", D("2862.00"), D(0)),
            (date(25, 9), "VIR 250926", "Règlement reçu", D(0), D("2862.00")),
            (date(24, 9), "FA-2026-0948", "Facture", D("1627.20"), D(0))], date(30, 9), D("1627.20")))

    # ---------------- bank statements and payment execution notices
    months = [(7, date(1, 7), date(31, 7), "2026-07"), (8, date(1, 8), date(31, 8), "2026-08"),
              (9, date(1, 9), date(30, 9), "2026-09"), (10, date(1, 10), date(9, 10), "2026-10")]
    for b in w.bank:
        x = b.payment
        if x and x.method == "DD":
            b.detail = f"PRÉLÈVEMENT SEPA CORE – CRÉANCIER {x.payee_name.upper()} – RUM AMS-{x.payee}-2024-01"
        elif x:
            b.detail = f"RÉF. DONNEUR D'ORDRE : {x.ref} – BÉNÉFICIAIRE : {x.payee_name.upper()}"
        elif b.category == "customer":
            b.detail = "DONNEUR D'ORDRE : " + b.label.split("RECU ")[1].split(" MGMT")[0].split(" RECHARGE")[0]
        elif b.category == "payroll":
            b.detail = f"VIREMENT GROUPÉ – LOT SAL-2026-{b.date:%m} – 42 OPÉRATIONS"
        elif b.category == "social":
            b.detail = "PRÉLÈVEMENT SEPA B2B – CAISSES SOCIALES – EMPLOYEUR N° 00418-27"
        elif b.category == "tax":
            b.detail = "TÉLÉRÈGLEMENT – SERVICE DES IMPÔTS – RÉF. TVA FR 64 000 512 748"
    bal = w.opening_bank
    for m, d1, d2, num in months:
        lines = [b for b in w.bank if d1 <= b.date <= d2]
        opening = bal
        bal = opening + sum((b.credit - b.debit for b in lines), D(0))
        add(f"bank:{num}", "bank_statement", f"Bank statement {num}{' (partial, to 09/10/2026)' if m == 10 else ''}",
            BANK["name"], E["AMS"]["name"], d2, "fr",
            lambda p, lines=lines, opening=opening, d1=d1, d2=d2, num=num: R.render_bank_statement(
                p, lines, opening, d1, d2, num, BANK, E["AMS"]))
    sept_transfers = [x for x in w.payments if x.method == "SEPA" and x.date.month == 9]
    by_day: dict = {}
    for x in sept_transfers:
        by_day.setdefault(x.date, []).append(x)
    for k, (d, ps) in enumerate(sorted(by_day.items()), 1):
        bid = f"LOT-2609-{k:02d}"
        add(f"batch:{bid}", "payment_execution_notice", f"Payment execution notice {bid}", BANK["name"], E["AMS"]["name"], d,
            "fr", lambda p, bid=bid, d=d, ps=ps: R.render_payment_batch(p, bid, d, ps, BANK, E["AMS"]))

    # ---------------- accounting exports
    labels = {6: "Juin 2026", 7: "Juillet 2026", 8: "Août 2026", 9: "Septembre 2026"}
    for m in (7, 8, 9):
        add(f"journal:{m}", "purchase_journal", f"Purchase journal (AC) {labels[m]}", E["AMS"]["name"], "internal",
            date(1, m + 1) if m < 12 else date(31, 12), "fr",
            lambda p, m=m: R.render_journal(p, journal(w, m), labels[m], E["AMS"], dt.datetime(2026, m + 1, 1, 8, 42)))
    accounts = []
    for code, s in sorted(SUPPLIERS.items(), key=lambda kv: kv[1].account):
        ent = ledger_entries(w, code)
        opening = sum((c - d for (dd, _, _, d, c) in ent if dd < date(1, 7)), D(0))
        sept = [e for e in ent if date(1, 7) <= e[0] <= date(30, 9)]
        if not sept and opening == 0:
            continue
        accounts.append((s.account, s.name, opening, sept, opening + sum((c - d for (_, _, _, d, c) in sept), D(0))))
    add("ledger:9", "ap_ledger", "Accounts payable ledger (401) July-September 2026", E["AMS"]["name"], "internal", date(1, 10),
        "fr", lambda p: R.render_ledger(p, accounts, "Du 01/07/2026 au 30/09/2026", E["AMS"], dt.datetime(2026, 10, 1, 8, 47)))
    at = date(30, 9)
    aged_rows = []
    for i, amt, k in sorted(open_items(w, at), key=lambda t: (t[0].s.account, t[0].date, t[2])):
        late = (at - i.due).days
        b = [D(0)] * 5
        idx = 0 if late <= 0 else 1 if late <= 30 else 2 if late <= 60 else 3 if late <= 90 else 4
        b[idx] = amt
        aged_rows.append((i.s.account, i.s.name, i.number, i.date, i.due, *b))
    add("aged:0930", "aged_payables", "Aged payables at 30/09/2026", E["AMS"]["name"], "internal", date(1, 10), "fr",
        lambda p: R.render_aged(p, aged_rows, at, E["AMS"], dt.datetime(2026, 10, 1, 8, 51)))
    add("master", "supplier_master_file", "Supplier master file", E["AMS"]["name"], "internal", date(1, 9), "fr",
        lambda p: R.render_master(p, sorted(SUPPLIERS.values(), key=lambda s: s.account), E["AMS"], dt.datetime(2026, 9, 1, 7, 55)))

    # ---------------- e-mails
    def mail(key, d, frm, to, subject, body, cc="", att=(), sender="", lang="en", reply_to="", in_reply_to=""):
        add(f"mail:{key}", "email", subject, frm, to, d.date(), lang,
            lambda p: R.write_eml(p, frm, to, d, subject, body, cc, sender, lang, reply_to, in_reply_to), ext="eml")

    po = {k: v.number for k, v in w.pos.items()}
    mail("marina", ts(date(28, 9), 9, 14), EMAILS["accounting"], EMAILS["operations"], "Marina Fuel – September invoice",
         "Hello Thomas,\n\nThe bank statement shows a payment of EUR 13,200.00 on 22/09/2026 with the reference "
         "\"INV 1182\" to Marina Fuel Services S.A.M.\n\nInvoice INV-2026-1182 dated 12/09/2026 is for EUR 26,400.00 "
         "(11,000 L of MGO delivered to M/Y Aurelia).\n\nCan you confirm whether the remaining EUR 13,200.00 is expected "
         "to be paid later, or whether the invoice should be split between two vessels? I have not found anything in the "
         "file on this point.\n\nThanks,\nInès Morel\nChief Accountant – Azur Marine Services S.A.M.",
         cc=EMAILS["fd"], sender="Inès Morel")
    mail("lme_bank", ts(date(14, 9), 11, 2), "amministrazione@lme-sanremo-it.example", EMAILS["ap"],
         "Updated bank details – Liguria Marine Electronics",
         "Dear customer,\n\nPlease note that, following the migration of our treasury to a new banking partner, all payments "
         "must from now on be made to the following account:\n\nBeneficiary: Liguria Marine Electronics S.r.l.\n"
         f"IBAN: {LME_NEW_IBAN}\nBIC: {LME_NEW_BIC}\n\nOur previous account will be closed on 15/09/2026. Please update your "
         "records before paying invoice LME-26-0611 and confirm by return e-mail.\n\nBest regards,\nGiulia Ferraro\n"
         "Ufficio Amministrazione – Liguria Marine Electronics S.r.l.", att=["Bank_confirmation_letter.pdf"],
         sender="Amministrazione LME", reply_to="giulia.ferraro.lme@mail-box.example")
    mail("lme_reply", ts(date(15, 9), 9, 40), EMAILS["ap"], "amministrazione@lme-sanremo-it.example",
         "RE: Updated bank details – Liguria Marine Electronics",
         "Dear Giulia,\n\nNoted, thank you. The new bank details have been entered in our payment system and will be used "
         "for the next payment run.\n\nKind regards,\nSofia Bianchi\nAccounts Payable – Azur Marine Services S.A.M.",
         sender="Sofia Bianchi")
    mail("cas_dup", ts(date(21, 9), 15, 26), cas.email, EMAILS["ap"], "Duplicata facture FA-2026-0917",
         "Madame, Monsieur,\n\nSuite à notre échange téléphonique de ce jour, vous trouverez ci-joint un duplicata de notre "
         "facture FA-2026-0917 du 03/09/2026, d'un montant de 2 862,00 € TTC (échéance 03/10/2026), que vous nous indiquez "
         "ne pas retrouver dans votre système.\n\nNous restons à votre disposition.\n\nCordialement,\nService comptabilité – "
         "Côte d'Azur Ship Chandlers SAS", att=["FA-2026-0917_duplicata.pdf"], sender="Comptabilité CASC", lang="fr")
    mail("captain", ts(date(6, 9), 19, 32), EMAILS["captain"], EMAILS["operations"],
         "Bilge pump failure on board M/Y Aurelia",
         "Thomas,\n\nThe main bilge pump failed this morning while the guests were on board. Northstar Yacht Services sent a "
         "technician who replaced the pump this afternoon; the yacht is safe and the bilge alarm has been reset.\n\nGiven the "
         "urgency I authorised the work verbally. The office was closed, so no purchase order was raised. Northstar will "
         "send their invoice directly to accounts.\n\nBest regards,\nCapt. James Whitfield\nMaster, M/Y Aurelia",
         sender="Capt. James Whitfield")
    mail("rve_order", ts(date(26, 8), 10, 5), SUPPLIERS["RVE"].email, EMAILS["ops"],
         f"Confirmation de commande {po['rve_aug']} – vidéosurveillance M/Y Aurelia",
         f"Bonjour Monsieur Rinaldi,\n\nNous accusons réception de votre bon de commande {po['rve_aug']} du 25/08/2026 "
         "(devis DEV-RE-2026-0457). Conformément aux conditions de la commande, un acompte de 30 % du montant TTC, soit "
         "5 112,00 €, est payable à la commande ; il sera déduit de la facture finale. L'installation est planifiée la "
         "semaine 38.\n\nBien cordialement,\nAdministration des ventes – Riviera Electronics SAS",
         sender="ADV Riviera Electronics", lang="fr")
    mail("seaglass_cn", ts(date(2, 9), 16, 48), SUPPLIERS["SEA"].email, EMAILS["ap"],
         "Credit note SG-CN-2026/0112 – damaged tins",
         "Dear Sirs,\n\nFurther to the reserve noted on delivery (CMR of 14/08/2026), please find attached credit note "
         "SG-CN-2026/0112 for EUR 620.00 covering the 4 damaged tins of Antifouling Pro-X red 2.5 L.\n\nThe balance due on "
         "invoice SG-2026/0877 is therefore EUR 7,840.00.\n\nKind regards,\nUfficio Amministrazione – SeaGlass Coatings S.r.l.",
         att=["SG-CN-2026-0112.pdf"], sender="SeaGlass Coatings")
    mail("med_0418", ts(date(2, 10), 8, 37), med.email, EMAILS["ap"], "September invoice INV-2026-0418",
         "Good morning,\n\nPlease find attached our invoice INV-2026-0418 dated 30/09/2026 for the engine-room consumables "
         "delivered on 25/09/2026 (EUR 15,360.00 incl. VAT). Apologies for sending it late.\n\nBest regards,\nBilling – "
         "Mediterra Marine Supplies S.A.M.", att=["INV-2026-0418.pdf"], sender="Mediterra Billing")
    mail("mrs_0298", ts(date(6, 10), 14, 12), SUPPLIERS["MRS"].email, EMAILS["ap"], "Invoice MRS-2026-0298 – M/Y Selene rigging",
         "Dear Accounts team,\n\nPlease find attached invoice MRS-2026-0298 dated 29/09/2026 for the standing rigging works "
         "completed on M/Y Selene on 24/09/2026.\n\nKind regards,\nOffice – Monaco Rigging & Sails S.A.R.L.",
         att=["MRS-2026-0298.pdf"], sender="Monaco Rigging & Sails")
    mail("vpn", ts(date(29, 9), 9, 55), SUPPLIERS["VPN"].email, EMAILS["ops"], f"Livraison compresseurs – commande {po['vpn_sep']}",
         "Bonjour,\n\nNos deux compresseurs haute pression ont été livrés hier à bord de M/Y Selene (BL VP-BL-26-0544). La "
         "facture sera émise début octobre avec notre cycle de facturation mensuel.\n\nCordialement,\nVar Pneumatique SAS",
         sender="Var Pneumatique", lang="fr")
    mail("prh", ts(date(10, 9), 17, 20), SUPPLIERS["PRH"].email, EMAILS["ops"], f"Reliquat commande {po['prh_sep']}",
         "Bonjour,\n\nSuite à une rupture chez notre fabricant, 4 flexibles FHP-12-2 n'ont pas pu être livrés ce jour "
         "(BL-PH-26-1187). Le reliquat sera livré semaine 41.\n\nCordialement,\nProvence Hydraulique SARL",
         sender="Provence Hydraulique", lang="fr")
    mail("close", ts(date(1, 9), 8, 30), EMAILS["fd"], "finance-team@azurmarine.example", "September 2026 close – calendar and cut-off",
         "Dear all,\n\nThe September close will follow the usual calendar:\n- Invoices received up to and including 30/09 are "
         "booked in the September purchase journal (AC).\n- Supplier invoices dated in September, or relating to goods or "
         "services delivered in September, that are received after 30/09 must be listed for accrual.\n- Goods or services "
         "received by 30/09 without an invoice are accrued at the PO price (net of VAT).\n- Bank reconciliation and supplier "
         "statement reconciliations (Mediterra, Oceanic Safety, Côte d'Azur Ship Chandlers) are due on 05/10.\n\nThanks,\n"
         "Claire Martin\nFinance Director", sender="Claire Martin")
    mail("kairos_dispute", ts(date(3, 7), 11, 18), EMAILS["fd"], SUPPLIERS["KIT"].email, "Invoice KIT-2026-0602 – disputed",
         "Dear Kairos team,\n\nWe do not accept invoice KIT-2026-0602 dated 01/06/2026 (11 additional engineering hours, "
         "EUR 1,320.00 incl. VAT). These hours were not ordered and the server migration is included in the fixed-fee scope "
         "of our managed services agreement (MSA-2022-07, schedule B). Please issue a credit note.\n\nBest regards,\n"
         "Claire Martin\nFinance Director – Azur Marine Services S.A.M.", sender="Claire Martin")
    mail("ose_pf", ts(date(20, 8), 13, 2), ose.email, EMAILS["ops"], "Pro-forma OSE-PF-2026-044 for approval",
         "Dear Mr Rinaldi,\n\nAs requested, please find attached our pro-forma OSE-PF-2026-044 (EUR 6,200.00, intra-EU supply) "
         "for the annual replenishment of safety equipment on M/Y Aurelia. Upon receipt of your purchase order we will ship "
         "within 2 weeks; the commercial invoice will follow shipment.\n\nMit freundlichen Grüßen,\nOceanic Safety Europe GmbH",
         att=["OSE-PF-2026-044.pdf"], sender="Oceanic Safety Europe")
    mail("nts_renewal", ts(date(2, 9), 10, 40), SUPPLIERS["NTS"].email, EMAILS["ops"], "ECDIS maintenance renewal 2026/2027",
         "Dear customer,\n\nYour ECDIS software maintenance and chart data subscription for 3 vessels expire on 30/09/2026. "
         "Please find attached our quotation NTS-Q-2026-0219 (EUR 24,500.00, reverse charge) for the period 01/10/2026 – "
         "30/09/2027. A purchase order is required before 15/09/2026 to avoid any interruption.\n\nBest regards,\nNavTech "
         "Systems GmbH – Customer Accounts", att=["NTS-Q-2026-0219.pdf"], sender="NavTech Billing")
    mail("harbor_ack", ts(date(2, 9), 7, 58), SUPPLIERS["HAR"].email, EMAILS["ops"], f"Order acknowledgement – your PO {po['har_sep']}",
         f"Dear Mr Rinaldi,\n\nThank you for your purchase order {po['har_sep']} dated 01/09/2026. We confirm availability of "
         "all items. Estimated dispatch: 08/09/2026, delivery DAP Monaco.\n\nPayment terms: 14 days net from invoice date.\n\n"
         "Kind regards,\nOrder desk – Harbor Parts B.V.", sender="Harbor Parts Order Desk")
    # noise e-mails
    mail("kairos_maint", ts(date(15, 9), 16, 0), "noc@kairos-it.example", "all-staff@azurmarine.example",
         "Planned maintenance window – Saturday 26/09/2026",
         "Hello,\n\nWe will upgrade the firewall firmware and the office Wi-Fi controllers on Saturday 26/09/2026 between "
         "07:00 and 11:00 CET. Remote access (VPN) will be unavailable during this window. Vessel connectivity is not "
         "affected.\n\nKairos IT Services – Network Operations Centre", sender="Kairos NOC")
    mail("lunch", ts(date(18, 9), 12, 5), "hr@azurmarine.example", "all-staff@azurmarine.example", "Team lunch – Friday 2 October",
         "Dear colleagues,\n\nTo celebrate the end of the summer season, the management invites the whole office team to "
         "lunch on Friday 2 October at 12:30 at the Yacht Club terrace. Please confirm your attendance by Wednesday.\n\n"
         "Human Resources", sender="Human Resources")
    mail("owner_calendar", ts(date(10, 9), 18, 44), "office@aurelia-yachting.example", EMAILS["ceo"], "Aurelia – winter programme",
         "Dear Philippe,\n\nThe owner confirms the winter programme: yard period in La Ciotat from 16/11/2026 to 20/01/2027, "
         "then Caribbean season departing Gibraltar on 05/02/2027. Please send the updated budget for the yard period by "
         "the end of October.\n\nBest regards,\nAurelia Yachting Ltd – Owner's office", sender="Aurelia Yachting Ltd")
    mail("bank_fees", ts(date(23, 9), 9, 0), "no-reply@brm-bank.example", EMAILS["fd"], "Évolution de nos conditions tarifaires au 01/01/2027",
         "Madame, Monsieur,\n\nNous vous informons qu'à compter du 01/01/2027, les frais de tenue de compte professionnel "
         "passeront de 45,00 € à 49,00 € par mois. Les virements SEPA unitaires restent facturés 0,50 €. La brochure "
         "tarifaire complète est disponible dans votre espace client.\n\nBanque Riviera Monaco – Service clientèle "
         "entreprises", sender="Banque Riviera Monaco", lang="fr")

    # ---------------- policies, contracts and other reference documents
    add("policy:procurement", "policy", "Procurement and payment policy PRC-FIN-04", E["AMS"]["name"], "internal", date(15, 1),
        "en", with_public_annex(lambda p: R_policy(p), "policy:procurement"))
    specs[-1].meta = {"public_annex_source": PUBLIC_ANNEXES["policy:procurement"][3],
                      "public_annex_licence": "European Commission reuse policy (Decision 2011/833/EU)"}

    def R_policy(p): return R.render_text_doc(p, "Procurement and payment policy", "Azur Marine Services S.A.M. – Finance",
              [("1. Purpose and scope", "This policy defines how goods and services are ordered, received, invoiced and "
                "paid by Azur Marine Services S.A.M. It applies to all purchases made for the office and for the vessels "
                "under management, whatever the amount. It does not apply to payroll, social contributions and taxes."),
               ("1.1 Definitions", ["Purchase order (PO): the written commitment issued by the company to a supplier, "
                "numbered PO-YYYY-NNNN and approved according to section 3. Delivery note: the supplier's document "
                "accompanying goods, signed on board on receipt. Service report: the document recording works performed "
                "on board, signed by the Master or the Chief Engineer. Supplier master file: the reference list of "
                "suppliers, their VAT numbers, bank details, payment terms and PO requirement, maintained by Finance.",
                "Net amount: amount excluding VAT. Deposit: a payment made before delivery or invoicing under an express "
                "clause of a signed PO or contract."]),
               ("1.2 Roles and responsibilities", ["Requesters (Masters, Chief Engineers, Operations) express the need "
                "and check receipt. The Operations Manager raises purchase orders and approves within his limit. The "
                "Finance Director approves within her limit, validates every payment run and owns the supplier master "
                "file. The Chief Executive Officer approves commitments above the Finance Director's limit.",
                "Accounts Payable books invoices only after the controls of section 5 and prepares payment runs; it may "
                "not modify supplier bank details without the confirmation described in section 6. Segregation of duties "
                "is mandatory: the person who enters a payment cannot approve it."]),
               ("2. Purchase orders", ["A purchase order (PO) approved in accordance with section 3 must be issued before "
                "any commitment towards a supplier flagged \"PO required = Yes\" in the supplier master file. Recurring "
                "services under a framework contract (berths, telecommunications, insurance, IT managed services, cleaning, "
                "provisions, crew agency) are exempt.", "In an emergency affecting the safety of a vessel, the Master may "
                "authorise work verbally; a regularisation PO must then be issued within 2 working days."]),
               ("3. Approval matrix", ["The approver is determined by the net amount (excluding VAT) of the PO. A higher "
                "level may always approve a lower amount.",
                ("table", [("Net amount of the PO (EUR)", 70 * R.mm, "l"), ("Required approver", 50 * R.mm, "l"),
                           ("Current holder", 50 * R.mm, "l")],
                 [["up to 5,000.00", "Operations Manager", "Thomas Rinaldi"],
                  ["5,000.01 to 20,000.00", "Finance Director", "Claire Martin"],
                  ["above 20,000.00", "Chief Executive Officer", "Philippe Andrieu"]])]),
               ("4. Receipt of goods and services", "Goods are received against a delivery note signed on board; services "
                "against a service report signed by the Master or the Chief Engineer. Partial deliveries must be recorded "
                "with the quantities actually received."),
               ("5. Invoice control (three-way match)", ["Before booking, each invoice is matched with the PO and the "
                "delivery note or service report. Quantities invoiced may not exceed quantities received. Prices may not "
                "exceed PO prices. VAT must be arithmetically correct and the invoice must carry the mandatory mentions.",
                "Any difference is put on hold and notified to the supplier in writing."]),
               ("6. Payments", ["Payments are made on or shortly before the due date. Payments before receipt of the "
                "invoice or of the goods are only allowed when a deposit or prepayment is expressly provided for in a signed "
                "PO or contract.", "Any change of supplier bank details must be confirmed by a call-back to the telephone "
                "number recorded in the supplier master file, by a person other than the requester, before the next payment."]),
               ("7. Period-end cut-off", "Invoices received after the closing date that relate to goods or services "
                "delivered during the period are accrued. Goods or services received without an invoice are accrued at "
                "the PO price."),
               ("8. Supplier master data", ["New suppliers are created only after the onboarding checks (registration "
                "extract, VAT number checked on VIES, bank identity statement on the supplier's letterhead, call-back). "
                "The master file records for each supplier whether a PO is required.", "Inactive suppliers are blocked "
                "after 24 months without transactions."]),
               ("9. Emergency purchases", "Emergency purchases made on the Master's verbal authorisation (section 2) "
                "must be documented by an e-mail from the Master on the same day and regularised by a PO within 2 "
                "working days. The supplier's invoice is not paid before regularisation."),
               ("10. Records", "Purchase orders, delivery notes, service reports, invoices and payment evidence are "
                "kept for 10 years in the document management system, one document per file, with their e-mails."),
               ("11. Breaches", "Any breach of this policy is reported to the Finance Director, who informs the CEO and, "
                "for amounts above EUR 20,000.00, the Board."),
               ("Annex A – Invoice checklist", [("table", [("Check", 70 * R.mm, "l"), ("Source", 60 * R.mm, "l"),
                                                           ("Owner", 40 * R.mm, "l")],
                 [["PO exists and is approved", "PO / supplier master file", "Accounts Payable"],
                  ["Goods or services received", "Delivery note / service report", "Accounts Payable"],
                  ["Quantities and prices", "PO and delivery note", "Accounts Payable"],
                  ["VAT arithmetic and mentions", "Invoice", "Accounts Payable"],
                  ["Not already booked", "Purchase journal", "Accounts Payable"],
                  ["Bank details", "Supplier master file", "Finance Director"]])]),
               ("Annex B – Document retention", [("table", [("Document", 80 * R.mm, "l"), ("Retention", 40 * R.mm, "l")],
                 [["Purchase orders, invoices, credit notes", "10 years"], ["Delivery notes, service reports", "10 years"],
                  ["Bank statements and payment notices", "10 years"], ["Supplier correspondence", "5 years"]])])]
              + LD.POLICY_MORE, date(15, 1), ref="PRC-FIN-04 v3", breaks=POLICY_BREAKS, subtitle="Approved by the Board on 15/01/2026")
    add("contract:berth", "contract", "Berth rental agreement M/Y Aurelia", SUPPLIERS["MBM"].name, E["AMS"]["name"], date(18, 12, 2025),
        "en", lambda p: R.render_text_doc(p, "Annual berth rental agreement – Berth B-14, Quai Antoine Ier",
              SUPPLIERS["MBM"].name, [
                  ("Parties", "Monaco Berth Management S.A.M. (the \"Operator\") and Azur Marine Services S.A.M., acting as "
                   "manager of M/Y Aurelia (the \"Client\")."),
                  ("1. Berth", "Berth B-14, maximum length 55 m, beam 10 m, draught 4.5 m, with shore power 400 V / 250 A, "
                   "fresh water and black-water pump-out."),
                  ("2. Term", "From 01/01/2026 to 31/12/2026, renewable by written agreement."),
                  ("3. Fee", "EUR 4,800.00 per month excluding VAT, invoiced on the first day of each month and collected by "
                   "SEPA direct debit on the tenth day. Electricity and water are invoiced separately on meter readings."),
                  ("4. Obligations", ["The Client shall comply with the port regulations and keep valid hull & machinery "
                   "and P&I insurance.", "The Operator may relocate the vessel temporarily for events (Grand Prix, Yacht "
                   "Show) with 15 days' notice."]),
                  ("5. Utilities", "Electricity is invoiced monthly at EUR 0.31 per kWh and water at EUR 6.80 per m3 on "
                   "meter readings, on a separate invoice."),
                  ("6. Services included", ["Mooring assistance on arrival and departure, 24/7 marina security, waste "
                   "reception (household waste only), Wi-Fi in the marina area.", "Oily waste, bilge water and hazardous "
                   "waste are excluded and must be handled by an approved contractor."]),
                  ("7. Liability and insurance", "The Operator is liable only for damage caused by its own negligence. The "
                   "Client indemnifies the Operator against claims arising from the vessel and its crew."),
                  ("8. Termination", "Either party may terminate for material breach after a formal notice remaining "
                   "unremedied for 30 days. Fees paid for the current month are not refunded."),
                  ("9. Law", "Monegasque law; courts of the Principality of Monaco."),
                  ("Signatures", "For the Operator: Harbour Master. For the Client: Philippe Andrieu, Chief Executive "
                   "Officer, Azur Marine Services S.A.M., on 18/12/2025.")] + LD.BERTH_MORE, date(18, 12, 2025),
              ref="MBM-AG-2026-014"))
    add("contract:kairos", "contract", "Managed services agreement MSA-2022-07 (extract)", SUPPLIERS["KIT"].name, E["AMS"]["name"],
        date(15, 1, 2022), "en", lambda p: R.render_text_doc(p, "Managed IT services agreement MSA-2022-07 – extract",
              SUPPLIERS["KIT"].name, [
                  ("Parties", "Kairos IT Services SAS, registered in Grasse under number 823 447 109 (\"Kairos\"), and "
                   "Azur Marine Services S.A.M., registered in Monaco under number RCI 09 S 05127 (\"the Customer\")."),
                  ("Clause 1 – Purpose", "Kairos provides managed IT services for the Customer's office at 7 Quai Antoine "
                   "Ier and for the vessels under the Customer's management, as described in the schedules. The schedules "
                   "form an integral part of the agreement; in case of conflict, the body of the agreement prevails."),
                  ("Clause 3 – Customer obligations", "The Customer appoints a single point of contact, gives Kairos "
                   "remote access to the systems in scope and informs Kairos of any change to its infrastructure. The "
                   "Customer remains responsible for the content of its data and for its licences."),
                  ("Schedule A – Services", "Service desk 08:00-19:00 on business days, monitoring 24/7, backup of office "
                   "servers, vessel connectivity support (3 vessels), Microsoft 365 administration."),
                  ("Schedule B – Projects included in the fixed fee", "Annual firewall upgrade; migration of on-premises "
                   "servers to the hosted platform (2026); onboarding of up to 10 new users per year."),
                  ("Schedule C – Fees", "Fixed monthly fee EUR 2,450.00 excluding VAT, payable by direct debit on the tenth "
                   "day of the month. Additional work only on written order at EUR 100.00 per hour."),
                  ("Schedule D – Service levels", [("table", [("Priority", 30 * R.mm, "l"), ("Definition", 80 * R.mm, "l"),
                                                              ("Response", 30 * R.mm, "l"), ("Resolution", 30 * R.mm, "l")],
                    [["P1", "Office or vessel without connectivity", "30 min", "4 h"],
                     ["P2", "Service degraded for several users", "2 h", "1 business day"],
                     ["P3", "Single user or request", "1 business day", "3 business days"]]),
                    "Service credits: 5% of the monthly fee per P1 incident resolved late, capped at 20% per month."]),
                  ("Clause 7 – Change requests", "Any work outside schedules A and B requires a written change request "
                   "signed by the customer's Finance Director before work starts. Work performed without a signed change "
                   "request is not chargeable."),
                  ("Clause 9 – Invoicing", "Kairos invoices the fixed fee on the first day of each month. Disputed "
                   "invoices are notified in writing within 30 days; the undisputed part remains payable."),
                  ("Clause 12 – Term", "Initial term of 36 months from 01/02/2022, renewed tacitly for 12-month periods "
                   "unless terminated with 3 months' notice."),
                  ("Clause 14 – Data protection", "Kairos acts as processor within the meaning of Regulation (EU) 2016/679 "
                   "and of Monegasque Law No. 1.565. Personal data are hosted in the European Union only."),
                  ("Clause 16 – Liability", "Kairos' aggregate liability per contract year is capped at the fees paid "
                   "during the previous twelve months, except in case of gross negligence or wilful misconduct."),
                  ("Signatures", "For Kairos IT Services SAS: the Managing Director. For the Customer: Claire Martin, "
                   "Finance Director, on 15/01/2022.")] + LD.KAIROS_MORE,
              date(15, 1, 2022), ref="MSA-2022-07"))
    add("contract:eco", "contract", "Waste collection framework contract CT-2024-118", SUPPLIERS["ECO"].name, E["AMS"]["name"],
        date(2, 12, 2024), "fr", lambda p: R.render_text_doc(p, "Contrat cadre de collecte des déchets d'exploitation CT-2024-118",
              SUPPLIERS["ECO"].name, [
                  ("Objet", "Collecte mensuelle des huiles usagées, filtres et chiffons souillés des navires gérés par Azur "
                   "Marine Services S.A.M. au port de Monaco."),
                  ("Prix", "Forfait mensuel de 640,00 € HT. Les prestations exceptionnelles (pompage, nettoyage de caisses) "
                   "font l'objet d'un devis et d'un bon de commande spécifiques."),
                  ("Durée", "Du 01/01/2025 au 31/12/2027."),
                  ("Obligations du prestataire", ["Le prestataire remet à chaque collecte un bordereau de suivi des déchets "
                   "(BSD) signé, mentionnant la nature et la quantité des déchets.", "Il justifie de son agrément pour la "
                   "collecte des huiles usagées et de son assurance responsabilité civile environnementale."]),
                  ("Facturation", "Le forfait mensuel est facturé le 20 de chaque mois, payable à 30 jours. Les prestations "
                   "exceptionnelles sont facturées à l'issue de l'intervention, sur la base du bon de commande."),
                  ("Résiliation", "Résiliation possible par lettre recommandée avec un préavis de trois mois."),
                  ("Signatures", "Pour EcoMarine Waste Services SAS : le Directeur général. Pour Azur Marine Services "
                   "S.A.M. : Thomas Rinaldi, Operations Manager, le 02/12/2024.")] + LD.ECO_MORE, date(2, 12, 2024),
              ref="CT-2024-118",
              color="#2E7D32"))
    add("onboarding:VPN", "supplier_onboarding", "Supplier onboarding form Var Pneumatique", E["AMS"]["name"], "internal",
        date(12, 9), "en", lambda p: R.render_text_doc(p, "Supplier onboarding form – Var Pneumatique SAS",
              "Azur Marine Services S.A.M. – Accounts Payable", [
                  ("Identification", ("table", [("Field", 60 * R.mm, "l"), ("Value", 110 * R.mm, "l")],
                   [["Legal name", "Var Pneumatique SAS"], ["Registration", "RCS Toulon 494 556 018"],
                    ["VAT ID", "FR 62 494 556 018"], ["IBAN", SUPPLIERS["VPN"].iban], ["BIC", SUPPLIERS["VPN"].bic],
                    ["Payment terms", "30 days net from invoice date"], ["PO required", "Yes"]])),
                  ("Checks performed", "Kbis extract dated less than 3 months, bank identity statement (RIB) on supplier "
                   "letterhead, VAT number checked on VIES on 12/09/2026, call-back to +33 4 94 30 12 65 performed by "
                   "S. Bianchi.")], date(12, 9), ref="ONB-2026-031"))

    noise = [
        ("lease", "contract", "Bail commercial – 7 Quai Antoine Ier", "SCI Port Lumière", date(30, 3, 2023), "fr", [
            ("Désignation", "Locaux à usage de bureaux d'une surface de 186 m² au 2e étage, avec deux emplacements de "
             "stationnement en sous-sol."),
            ("Durée", "Neuf années entières et consécutives à compter du 01/04/2023."),
            ("Loyer", "Loyer annuel de 96 000,00 € hors charges, payable trimestriellement et d'avance, indexé chaque année "
             "sur l'indice des loyers des activités tertiaires."),
            ("Dépôt de garantie", "24 000,00 €, correspondant à trois mois de loyer."),
            ("Charges", "Provision trimestrielle sur charges de 3 150,00 €, régularisée annuellement.")]),
        ("insurance", "insurance_policy", "Hull & machinery policy schedule HM-2026-0441", "Lighthouse Insurance Brokers S.A.M.",
         date(20, 12, 2025), "en", [
            ("Insured vessels", ("table", [("Vessel", 50 * R.mm, "l"), ("Agreed value EUR", 40 * R.mm, "r"), ("Deductible EUR", 40 * R.mm, "r")],
                                 [["M/Y Aurelia", "38,500,000.00", "150,000.00"], ["M/Y Selene", "17,200,000.00", "75,000.00"],
                                  ["S/Y Blue Horizon", "6,900,000.00", "40,000.00"]])),
            ("Period", "00:01 on 01/01/2026 to 24:00 on 31/12/2026."),
            ("Premium", "Annual premium EUR 75,000.00 payable in four quarterly instalments of EUR 18,750.00."),
            ("Navigation limits", "Mediterranean Sea and Caribbean; Atlantic crossings subject to prior notice.")]),
        ("board", "minutes", "Minutes of the Board meeting of 24/06/2026", "Azur Marine Services S.A.M.", date(24, 6), "en", [
            ("Attendance", "Present: P. Andrieu (Chairman and CEO), C. Martin (Finance Director, secretary), two independent "
             "directors. Quorum reached."),
            ("1. Half-year trading", "Management fees in line with budget; three new management mandates under negotiation."),
            ("2. Fleet", "Approval of the yard budget for M/Y Aurelia (winter 2026/27)."),
            ("3. Procurement", "The Board reaffirms the approval matrix of policy PRC-FIN-04 and asks Finance to report "
             "quarterly on purchase orders approved above delegated limits."),
            ("4. Any other business", "None. The meeting closed at 18:40.")]),
        ("it_policy", "policy", "Information security policy ISP-01", "Azur Marine Services S.A.M.", date(3, 3), "en", [
            ("Scope", "All employees, crew members using office systems and contractors."),
            ("Passwords and MFA", "Multi-factor authentication is mandatory for e-mail, banking and the accounting system."),
            ("Phishing", "Any e-mail requesting a change of bank details or an urgent payment must be reported to the "
             "Finance Director and verified by telephone."),
            ("Incidents", "Report any incident to Kairos IT Services within one hour.")]),
        ("survey", "survey_report", "Annual condition survey M/Y Aurelia", "Méditerranée Marine Surveyors", date(18, 5), "en", [
            ("Vessel", "M/Y Aurelia, 52 m motor yacht, built 2017, flag Cayman Islands, class LR."),
            ("Hull", "Hull plating and coating in good condition; minor blistering on starboard quarter to be monitored."),
            ("Machinery", "Main engines 2 x 1,940 kW, 11,820 running hours; oil analysis within limits."),
            ("Safety", "Liferafts due for service in September 2026; EPIRB battery expiry 10/2026."),
            ("Recommendations", "Renew shaft seals at next haul-out; service liferafts before 30/09/2026.")]),
        ("fuel_bulletin", "market_bulletin", "Riviera marine fuel price bulletin – September 2026", "Riviera Bunker Index",
         date(1, 9), "en", [("Average delivered prices (EUR per litre, excl. VAT)", ("table",
                             [("Product", 60 * R.mm, "l"), ("July", 30 * R.mm, "r"), ("August", 30 * R.mm, "r"), ("September", 30 * R.mm, "r")],
                             [["MGO DMA (truck)", "1.962", "1.988", "2.004"], ["MGO DMA (barge)", "1.874", "1.902", "1.915"],
                              ["Lube oil 15W-40", "3.420", "3.455", "3.470"]])),
                            ("Comment", "Prices remained stable over the summer; a slight increase is expected in Q4.")]),
        ("pricelist", "price_list", "Mediterra Marine Supplies – price list 2026", "Mediterra Marine Supplies S.A.M.", date(5, 1), "en", [
            ("Engine room", ("table", [("Code", 30 * R.mm, "l"), ("Description", 90 * R.mm, "l"), ("Price EUR", 30 * R.mm, "r")],
                             [["LO-1540-208", "Lube oil SAE 15W-40, 208 L drum", "742.00"], ["HO-46-208", "Hydraulic oil ISO VG 46, 208 L drum", "698.00"],
                              ["FF-5320", "Fuel filter element FF-5320", "38.50"], ["IMP-17937", "Impeller kit for raw-water pump", "186.00"],
                              ["CC-20", "Coolant concentrate, 20 L", "64.50"], ["OAP-200", "Oil absorbent pads (bale of 200)", "58.00"],
                              ["WP-500", "Engine-room wipes, industrial (box of 500)", "37.00"], ["GL-N100", "Nitrile gloves (box of 100)", "12.00"]])),
            ("Conditions", "Prices excluding VAT, delivery and handling EUR 320.00 per order in Monaco.")]),
        ("expo", "invitation", "Invitation – Riviera Yachting Expo 2026", "Riviera Yachting Expo", date(20, 8), "en", [
            ("", "Azur Marine Services S.A.M. is invited to the professional days of the Riviera Yachting Expo, from 23 to 26 "
             "September 2026. Your badges (4) can be collected at the accreditation desk."),
            ("Programme", "Conference on crew wellbeing (24/09), superyacht finance breakfast (25/09).")]),
        ("mgmt_q2", "management_report", "Management report Q2 2026", "Azur Marine Services S.A.M.", date(20, 7), "en", [
            ("Highlights", "Revenue from management fees for the quarter: EUR 912,000.00; recharges to owners: EUR 341,000.00."),
            ("Costs", "Personnel costs including social charges EUR 720,000.00; office, IT, insurance and professional fees "
             "EUR 61,000.00."),
            ("Outlook", "Q3 will be impacted by the yard preparation of M/Y Aurelia and the ECDIS renewal.")]),
        ("payroll", "payroll_summary", "Payroll summary September 2026", "Azur Marine Services S.A.M.", date(28, 9), "fr", [
            ("Synthèse", ("table", [("Rubrique", 90 * R.mm, "l"), ("Montant EUR", 40 * R.mm, "r")],
                          [["Salaires bruts", "118 214,30"], ["Cotisations salariales", "-31 793,75"], ["Net à payer (42 salariés)", "86 420,55"],
                           ["Cotisations patronales", "33 410,12"]])),
            ("Paiement", "Virement groupé le 30/09/2026.")]),
        ("vat_aug", "tax_return", "VAT return August 2026", "Azur Marine Services S.A.M.", date(18, 9), "fr", [
            ("Déclaration de TVA – période 08/2026", ("table", [("Ligne", 90 * R.mm, "l"), ("Montant EUR", 40 * R.mm, "r")],
                [["TVA collectée", "41 302,00"], ["TVA autoliquidée (acquisitions UE)", "3 296,00"],
                 ["TVA déductible sur biens et services", "-27 087,00"], ["TVA déductible autoliquidée", "-3 296,00"],
                 ["TVA nette due", "14 215,00"]])),
            ("Paiement", "Télérèglement le 21/09/2026.")]),
        ("fees", "bank_tariff", "Bank fee schedule 2026 – professional accounts", "Banque Riviera Monaco", date(2, 1), "fr", [
            ("Tenue de compte", "45,00 € par mois ; abonnement banque en ligne Pro : 18,00 € par mois."),
            ("Virements", "Virement SEPA unitaire : 0,50 € ; virement international hors SEPA : 25,00 €."),
            ("Incidents", "Commission d'intervention : 8,00 € par opération, plafonnée à 80,00 € par mois.")]),
        ("port_notice", "notice", "Port notice 2026-17 – Quai Antoine Ier works", "Capitainerie du Port", date(7, 9), "en", [
            ("", "Resurfacing works will take place on Quai Antoine Ier from 05/10/2026 to 16/10/2026. Vehicle access to berths "
             "B-10 to B-18 will be restricted between 08:00 and 17:00. Deliveries must be scheduled with the harbour master.")]),
        ("rotation", "crew_schedule", "Crew rotation schedule Q4 2026", "Azur Marine Services S.A.M.", date(15, 9), "en", [
            ("M/Y Aurelia", ("table", [("Position", 50 * R.mm, "l"), ("Rotation A", 50 * R.mm, "l"), ("Rotation B", 50 * R.mm, "l")],
                             [["Master", "J. Whitfield", "D. Okafor"], ["Chief Engineer", "R. Lindqvist", "P. Navarro"],
                              ["Chief Stewardess", "L. Moreau", "S. Ivanova"], ["Bosun", "A. Kowalski", "T. Reyes"]])),
            ("Rules", "Rotations of 10 weeks on / 10 weeks off; travel days are paid.")]),
        ("drill", "safety_report", "Safety drill report – M/Y Selene", "M/Y Selene", date(19, 8), "en", [
            ("Drill", "Abandon ship and fire drill held at 10:30 on 19/08/2026, Monaco."),
            ("Participants", "11 crew members; all present at muster station within 3 minutes."),
            ("Findings", "One lifejacket light inoperative (replaced); fire door 3 slow to close (adjusted).")]),
        ("stcw", "certificate", "Training certificate – advanced fire fighting", "Mediterranean Maritime Academy", date(4, 9), "en", [
            ("", "This is to certify that Marco Ferri has successfully completed the advanced fire fighting course (STCW "
             "Regulation VI/3) from 31/08/2026 to 04/09/2026.")]),
        ("charter", "contract", "Management agreement summary – S/Y Blue Horizon", "Azur Marine Services S.A.M.", date(1, 2), "en", [
            ("Scope", "Technical, crew and financial management of S/Y Blue Horizon."),
            ("Fee", "EUR 22,750.00 per month excluding VAT, invoiced on the first day of the month."),
            ("Recharges", "Third-party costs are recharged at cost with supporting documents.")]),
        ("expenses", "expense_report", "Expense report – T. Rinaldi – August 2026", "Azur Marine Services S.A.M.", date(31, 8), "fr", [
            ("Détail", ("table", [("Date", 25 * R.mm, "l"), ("Nature", 90 * R.mm, "l"), ("Montant TTC", 30 * R.mm, "r")],
                        [["04/08/2026", "Train Nice – Gênes (visite fournisseur)", "86,40"], ["04/08/2026", "Déjeuner fournisseur (2 pers.)", "74,00"],
                         ["19/08/2026", "Parking aéroport", "32,00"], ["Total", "", "192,40"]])),
            ("Validation", "Validé par C. Martin le 02/09/2026.")]),
        ("travel", "booking_confirmation", "Travel booking confirmation – crew change", "Seaview Travel Agency", date(21, 9), "en", [
            ("Booking", "Booking reference SVT-88213, 4 passengers Nice – Gibraltar, 29/09/2026, total EUR 1,612.00 charged to "
             "the company card.")]),
        ("audit", "engagement_letter", "Audit engagement letter 2026", "Cabinet Riviera Audit & Conseil", date(12, 5), "fr", [
            ("Mission", "Certification des comptes annuels de l'exercice clos le 31/12/2026."),
            ("Honoraires", "Honoraires forfaitaires de 28 500,00 € HT, facturés en trois fois."),
            ("Calendrier", "Intervention intérimaire en novembre 2026 ; intervention finale en mars 2027.")]),
        ("loan", "loan_schedule", "Loan amortisation schedule – office fit-out", "Banque Riviera Monaco", date(10, 1, 2025), "fr", [
            ("Prêt n° PR-2025-0119", "Capital emprunté 180 000,00 € sur 60 mois au taux fixe de 3,40 %."),
            ("Échéancier 2026", ("table", [("Échéance", 30 * R.mm, "l"), ("Capital", 35 * R.mm, "r"), ("Intérêts", 35 * R.mm, "r"), ("Total", 35 * R.mm, "r")],
                                 [["10/07/2026", "2 951,21", "312,43", "3 263,64"], ["10/08/2026", "2 959,57", "304,07", "3 263,64"],
                                  ["10/09/2026", "2 967,96", "295,68", "3 263,64"]])),
            ("Note", "Les échéances sont prélevées sur le compte de la société mère Azur Yachting Group S.A.M.")]),
        ("assets", "fixed_asset_register", "Fixed asset register extract 31/08/2026", "Azur Marine Services S.A.M.", date(5, 9), "fr", [
            ("Immobilisations", ("table", [("N°", 20 * R.mm, "l"), ("Désignation", 80 * R.mm, "l"), ("Valeur brute", 35 * R.mm, "r"), ("VNC", 35 * R.mm, "r")],
                                 [["IM-0041", "Agencement bureaux", "142 600,00", "98 210,00"], ["IM-0058", "Serveurs et réseau", "38 400,00", "12 800,00"],
                                  ["IM-0062", "Véhicule de service", "31 900,00", "15 950,00"]]))]),
    ]
    extra = {
        "lease": [("Indexation", "Le loyer est révisé automatiquement chaque 1er avril en fonction de la variation de "
                   "l'indice des loyers des activités tertiaires (ILAT) publié au cours du quatrième trimestre précédent. La "
                   "révision ne peut entraîner une baisse du loyer en deçà du loyer initial."),
                  ("Charges et impôts", ["Le preneur rembourse au bailleur, au prorata des surfaces louées, les charges "
                   "communes de l'immeuble : entretien des parties communes, ascenseurs, gardiennage, chauffage collectif, "
                   "taxe d'enlèvement des ordures ménagères.", "Un décompte annuel des charges est adressé au preneur avant "
                   "le 30 juin de chaque année ; le solde est réglé dans les 30 jours de sa réception."]),
                  ("Entretien et réparations", "Le preneur entretient les locaux en bon état de réparations locatives. "
                   "Les grosses réparations au sens de l'article 606 du Code civil restent à la charge du bailleur."),
                  ("Destination", "Les locaux sont destinés exclusivement à usage de bureaux pour l'activité de gestion de "
                   "navires de plaisance du preneur."),
                  ("Travaux", ["Le preneur ne peut effectuer aucun travail affectant le gros œuvre sans l'accord écrit du "
                   "bailleur.", "Les travaux d'aménagement réalisés en 2023 (cloisons, câblage, climatisation) restent "
                   "acquis au bailleur en fin de bail sans indemnité."]),
                  ("Assurances", "Le preneur assure les locaux contre l'incendie, le dégât des eaux et sa responsabilité "
                   "civile, et justifie de ses polices à première demande."),
                  ("Cession et sous-location", "Toute cession ou sous-location est interdite sans l'accord exprès du "
                   "bailleur, sauf au profit d'une société du groupe Azur Yachting."),
                  ("Clause résolutoire", "À défaut de paiement d'un seul terme de loyer à son échéance, et un mois après "
                   "commandement resté infructueux, le bail sera résilié de plein droit."),
                  ("Fait à Monaco", "Le 30 mars 2023, en deux exemplaires originaux.")],
        "insurance": [("Insured perils", ["Perils of the seas, fire, explosion, theft by persons from outside the vessel, "
                       "jettison, piracy, contact with aircraft or land conveyance, earthquake and lightning.",
                       "Accidents in loading, discharging or shifting stores, bursting of boilers, latent defects in the "
                       "machinery or hull, negligence of Master, officers or crew, provided such loss has not resulted from "
                       "want of due diligence by the assured or managers."]),
                      ("Machinery damage deductible", "An additional deductible of EUR 25,000.00 applies to each claim for "
                       "machinery damage caused by negligence of the crew or latent defect."),
                      ("Main exclusions", ["War, strikes and terrorism (covered under separate war risks cover).",
                       "Wear and tear, gradual deterioration, marine growth.", "Unseaworthiness known to the assured."]),
                      ("Claims procedure", "Any incident likely to give rise to a claim must be notified to the broker "
                       "within 72 hours, with the Master's report and photographs."),
                      ("Security", "100% Riviera Marine Mutual (lead) and following markets.")],
        "board": [("4bis. Management mandates", ["The CEO reports on the negotiation of a management mandate for a 45 m "
                   "motor yacht based in Antibes, through the sister company Azur Marine Charter SARL. Expected fee: "
                   "EUR 26,000.00 per month excluding VAT from January 2027.", "The Board authorises the CEO to sign the "
                   "mandate within these parameters."]),
                  ("4ter. Insurance renewal", "The Finance Director presents the renewal terms proposed by Lighthouse "
                   "Insurance Brokers for 2027: premium increase of 4.5% on hull & machinery; P&I unchanged. The Board "
                   "asks for a competing quotation before 31/10/2026."),
                  ("5. Treasury", "Cash position at 31/05/2026: EUR 438,200.00; no drawing on the overdraft facility."),
                  ("6. Internal control", "Finance presents the results of the 2025 audit: no significant deficiency; one "
                   "recommendation on the documentation of emergency purchases on board."),
                  ("7. Dates", "Next meetings: 22/09/2026 and 15/12/2026.")],
        "survey": [("Machinery details", ("table", [("Item", 60 * R.mm, "l"), ("Condition", 40 * R.mm, "l"), ("Action", 60 * R.mm, "l")],
                    [["Port main engine", "Good", "Routine service at 12,000 h"], ["Starboard main engine", "Good", "Routine service at 12,000 h"],
                     ["Generator 1", "Fair", "Replace exhaust elbow"], ["Generator 2", "Good", "None"],
                     ["Bilge pumps", "Fair", "Main pump close to end of life"], ["Steering gear", "Good", "None"]])),
                   ("Electrical", "24 V and 230 V systems in good order; shore power connection to be inspected."),
                   ("Conclusion", "The vessel is in good condition and suitable for its intended use, subject to the "
                    "recommendations above. Surveyor: J.-M. Castel, Méditerranée Marine Surveyors.")],
        "mgmt_q2": [("Income statement Q2 2026 (EUR thousand)", ("table", [("Line", 70 * R.mm, "l"), ("Q2 2026", 30 * R.mm, "r"),
                     ("Q2 2025", 30 * R.mm, "r")],
                     [["Management fees", "912", "874"], ["Recharges to owners", "341", "318"], ["Recharged costs", "(341)", "(318)"],
                      ["Personnel costs incl. social charges", "(720)", "(689)"], ["Office, IT, insurance, fees", "(61)", "(58)"],
                      ["Travel and other external costs", "(57)", "(54)"], ["Depreciation", "(9)", "(9)"],
                      ["Operating result", "65", "64"]])),
                    ("Key risks", "Concentration on three owners; dependence on key crew; IT security incidents (phishing).")],
        "audit": [("Responsabilités", "La direction est responsable de l'établissement des comptes et du contrôle interne. "
                   "L'auditeur exprime une opinion sur les comptes annuels."),
                  ("Équipe", "Associé signataire, un manager et deux auditeurs ; interlocuteur principal : Claire Martin."),
                  ("Contrôle interne", "Les travaux intérimaires porteront notamment sur le cycle achats-fournisseurs : "
                   "séparation des tâches, approbation des commandes, modification des coordonnées bancaires, rapprochements "
                   "bancaires et procédures de clôture.")],
    }
    extra["lease"] = LD.LEASE_MORE + extra.get("lease", [])
    extra["lease"] += LD.lease_inventory()
    for k, more in {"insurance": LD.insurance_more() + LD.insurance_claims(), "board": LD.BOARD_MORE[:1], "it_policy": LD.IT_MORE,
                    "survey": LD.survey_more() + LD.survey_zones(), "pricelist": LD.pricelist_more(), "mgmt_q2": LD.mgmt_q2_more(),
                    "vat_aug": LD.vat_more(), "audit": LD.AUDIT_MORE,
                    "loan": LD.loan_schedule()}.items():
        extra[k] = extra.get(k, []) + more
    noise = [n for n in noise if n[0] not in DROPPED_NOISE]
    noise += [("internal_audit", "audit_report", "Internal audit report – purchase-to-pay cycle 2025",
               "Riviera Internal Audit Services", date(28, 11, 2025), "en", LD.internal_audit_2025() + LD.audit_samples()),
              ("annual_accounts", "financial_statements", "Comptes annuels 2025 – Azur Marine Services S.A.M.",
               "Azur Marine Services S.A.M.", date(24, 3), "fr", LD.annual_accounts_2025()),
              ("mgmt_aug", "management_report", "Monthly management accounts – August 2026", "Azur Marine Services S.A.M.",
               date(15, 9), "en", LD.mgmt_accounts_aug())]
    for key, t, title, issuer, d, lang, sections in noise:
        if key == "loan":
            sections = sections[:1]  # the computed schedule replaces the 3-row extract
        sections = sections + ([] if key == "board" else extra.get(key, []))  # board minutes: one page
        add(f"noise:{key}", t, title, issuer, "internal" if issuer == "Azur Marine Services S.A.M." else E["AMS"]["name"], d, lang,
            lambda p, title=title, issuer=issuer, sections=sections, d=d, key=key: R.render_text_doc(
                p, title, issuer, sections, d, breaks=BREAKS.get(key, ())))

    # sales invoices issued by Azur Marine Services (sales cycle, not purchases)
    clients = {
        "01": (["Aurelia Yachting Ltd", "Harbour Place, 103 South Church Street", "George Town, Grand Cayman KY1-1106"], "48000.00"),
        "02": (["Selene Marine Holdings Ltd", "8 Ta' Xbiex Seafront", "XBX 1027 Ta' Xbiex, Malta"], "31500.00"),
        "03": (["Blue Horizon Yachts SA", "Rue du Rhône 62", "1204 Genève, Switzerland"], "22750.00")}
    for m in (8, 9):
        for c, (addr, amt) in clients.items():
            num = f"AMS-2026-{m:02d}{c}"
            gross = D(amt)
            net = (gross / D("1.20")).quantize(D("0.01"))
            add(f"sales:{num}", "sales_invoice", f"Sales invoice {num}", E["AMS"]["name"], addr[0], date(1, m), "en",
                lambda p, num=num, m=m, addr=addr, net=net: R.render_sales_invoice(
                    p, num, date(1, m), addr, [(f"Yacht management fee – {dt.date(2026, m, 1):%B %Y}", net)], E["AMS"]))
    add("sales:AMS-2026-0911", "sales_invoice", "Sales invoice AMS-2026-0911", E["AMS"]["name"], "Aurelia Yachting Ltd",
        date(8, 9), "en", lambda p: R.render_sales_invoice(p, "AMS-2026-0911", date(8, 9), clients["01"][0],
                                                          [("Recharge of third-party costs – August 2026 (detail attached)", D("34396.33"))], E["AMS"]))
    return w, specs


# ---------------------------------------------------------------- scanning

def scan(native: Path, out: Path, seed: int) -> None:
    rnd = random.Random(seed)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "150", "-gray", "-png", str(native), f"{td}/p"], check=True)
        pages = []
        for png in sorted(Path(td).glob("p*.png")):
            im = Image.open(png).convert("L")
            im = im.rotate(rnd.uniform(-1.4, 1.4), resample=Image.BICUBIC, expand=False, fillcolor=255)
            noise = Image.effect_noise(im.size, 18).convert("L")
            im = Image.blend(im, noise, 0.06)
            im = im.filter(ImageFilter.GaussianBlur(0.45))
            im = im.point(lambda v: max(0, min(255, int((v - 18) * 1.08))))
            # darker scanner edge on the left margin
            edge = Image.new("L", (14, im.size[1]), 120)
            im.paste(edge, (0, 0))
            pages.append(im.convert("RGB"))
        pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:], quality=72)


def pdf_text(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    return int(next(l for l in out.splitlines() if l.startswith("Pages:")).split()[1])


def main() -> int:
    w, specs = build_specs()
    keys = [s.key for s in specs]
    assert len(keys) == len(set(keys)), "duplicate document keys"
    random.Random(20260930).shuffle(specs)
    final_docs, final_ocr = DOCS, OCR
    docs_dir, ocr_dir = CORPUS / ".staging_documents", CORPUS / ".staging_ocr"
    for d in (docs_dir, ocr_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    manifest = []
    with tempfile.TemporaryDirectory() as td:
        for n, s in enumerate(specs, 1):
            doc_id = f"acc_doc_{n:03d}"
            out = docs_dir / f"{doc_id}.{s.ext}"
            if s.scanned:
                native = Path(td) / f"{doc_id}.pdf"
                s.draw(native)
                (ocr_dir / f"{doc_id}.txt").write_text(pdf_text(native), "utf-8")
                scan(native, out, seed=n)
                pages = page_count(native)
            else:
                s.draw(out)
                pages = page_count(out) if s.ext == "pdf" else 1
            data = out.read_bytes()
            manifest.append(dict(document_id=doc_id, filename=out.name, key=s.key, document_type=s.doc_type, title=s.title,
                                 issuer=s.issuer, addressee=s.addressee, document_date=s.doc_date.isoformat(),
                                 language=s.lang, pages=pages, scanned=s.scanned, sha256=hashlib.sha256(data).hexdigest(),
                                 bytes=len(data), **s.meta))
    for final, staged in ((final_docs, docs_dir), (final_ocr, ocr_dir)):  # every document built: swap in
        if final.exists():
            shutil.rmtree(final)
        staged.rename(final)
    body = {"corpus": "accountingbench_corpus_v1", "n_documents": len(manifest),
            "total_pages": sum(d["pages"] for d in manifest), "n_scanned": sum(d["scanned"] for d in manifest),
            "note": "Fictional documents generated by tools/generate_corpus.py. Ingest corpus/documents/ only: this "
                    "manifest, ocr_reference/ and the datasets are ground truth and must never be ingested.",
            "documents": manifest}
    text = json.dumps(body, indent=1, ensure_ascii=False)
    (CORPUS / "manifest.json").write_text(text, "utf-8")
    (CORPUS / "FROZEN.json").write_text(json.dumps({
        "manifest_sha256": hashlib.sha256(text.encode()).hexdigest(), "n_documents": len(manifest),
        "total_pages": body["total_pages"], "generator": "tools/generate_corpus.py"}, indent=2), "utf-8")

    # isolation probe: a document that must be ingested in ANOTHER store only (see README, T15)
    PROBE.mkdir(exist_ok=True)
    SUPPLIERS["KAF"] = Supplier(code="KAF", name="Kestrel Aviation Fuels Ltd", short="KESTREL AVIATION", street="Hangar 4, Biggin Hill Airport",
                                city="Westerham TN16 3BN", country="United Kingdom", vat_id="GB 318 4471 26",
                                reg="Company No. 08841723", iban="GB29 KEST 6016 1331 9268 19", bic="KESTGB2LXXX",
                                bank="Kestrel Treasury", email="billing@kestrel-fuels.example", phone="+44 1959 571 300",
                                terms=30, lang="en", style="modern", num="en", dstyle="slash", po_required=False,
                                account="-", expense="-", regime="RC", color="#880E4F", activity="Aviation fuel supply",
                                created=date(1, 1), logo="flame")
    helios = dict(name="Helios Air Charter SAS", street="Aéroport Nice Côte d'Azur, Terminal Aviation d'Affaires",
                  city="06200 Nice", country="France", vat_id="", vat="FR 44 902 118 330", reg="", nis="", capital="",
                  phone="", email="", web="")
    probe = Invoice("KAF-2026-7731", "KAF", date(17, 9), [L("Jet A-1, into-plane, tail F-HELI, Nice LFMN", 18650, "L", "2.607")],
                    customer="HELIOS")
    R.render_invoice(PROBE / "probe_doc_001.pdf", probe, {**ENTITIES, "HELIOS": helios}, w)
    del SUPPLIERS["KAF"]
    print(f"{len(manifest)} documents, {body['total_pages']} pages, {body['n_scanned']} scanned -> {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
