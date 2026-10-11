"""Realistic filling content for invoices, POs, delivery notes and payment notices (AccountingBench).

Deterministic (seeded by document numbers) and consistent with world.py: quantities, dates, vessels and suppliers come
from the world objects; nothing here changes an amount that a question asks about.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import random
from decimal import Decimal

from reportlab.lib.units import mm

from common import D, fdate, fmt

HS = [("antifouling", "3208.90", 1.4), ("primer", "3208.10", 6.2), ("thinner", "3814.00", 4.6), ("application kit", "9603.40", 1.8),
      ("lube oil", "2710.19", 186.0), ("hydraulic oil", "2710.19", 184.0), ("oil 2t", "2710.19", 0.9), ("fuel filter", "8421.23", 0.6),
      ("coolant", "3820.00", 21.5), ("impeller", "8413.91", 0.8), ("wipes", "4818.20", 4.2), ("pads", "5603.94", 9.5),
      ("gloves", "4015.19", 0.7), ("seal", "8484.20", 2.4), ("cutless", "8483.30", 3.1), ("coupling", "7318.15", 2.2),
      ("raw-water pump", "8413.91", 2.6), ("anode", "7907.00", 1.9), ("liferaft", "8907.10", 96.0), ("epirb", "8506.50", 0.9),
      ("lifejacket", "6307.20", 1.1), ("extinguisher", "8424.10", 10.5), ("pyrotechnic", "3604.90", 3.8), ("radar", "8529.90", 4.4),
      ("display", "8528.59", 7.9), ("nmea", "8544.42", 1.2), ("ais", "8526.91", 1.6), ("vhf antenna", "8529.10", 2.8),
      ("flexible", "4009.42", 0.9), ("raccord", "7307.22", 0.2), ("cordage", "5607.50", 14.0), ("défenses", "4016.94", 3.6),
      ("nettoyant", "3402.90", 5.4), ("gants", "6116.10", 0.8), ("manilles", "7326.19", 0.3), ("seaux", "7323.93", 1.1),
      ("ruban", "3919.10", 0.6), ("bidons", "2710.19", 0.9), ("vidéosurveillance", "8525.89", 9.8), ("enregistreur", "8521.90", 3.2),
      ("câblage", "8544.49", 18.0), ("compresseur", "8414.80", 64.0), ("vérin", "8412.21", 22.0), ("joints", "4016.93", 0.4),
      ("halyard", "5607.50", 4.0), ("shroud", "7312.10", 9.0), ("pompe", "8413.70", 4.8), ("chargeur", "8504.40", 7.5),
      ("tableau", "8537.10", 28.0), ("disjoncteurs", "8536.20", 0.4), ("éponges", "6805.30", 0.3)]


def _rnd(*keys) -> random.Random:
    return random.Random(int(hashlib.sha1("|".join(map(str, keys)).encode()).hexdigest()[:12], 16))


def hs_of(desc: str):
    d = desc.lower()
    for k, code, w in HS:
        if k in d:
            return code, w
    return None, None


def is_goods(inv) -> bool:
    return any(hs_of(ln.desc)[0] for ln in inv.lines)


def T(cols, rows):
    return ("table", cols, rows)


def _country(s):
    return {"Italy": "IT", "Netherlands": "NL", "Germany": "DE", "France": "FR", "Monaco": "MC", "Malta": "MT"}.get(s.country, "EU")


# ---------------------------------------------------------------- invoice page 1: logistics / customs / intervention summary
def invoice_page1_blocks(inv, w):
    """Blocks drawn under the payment details on page 1: [(title, [(label, value)…] | table)]."""
    s, r = inv.s, _rnd(inv.number)
    fr = s.lang == "fr"
    dn = w.dn(inv.dn) if inv.dn else None
    blocks = []
    if is_goods(inv):
        weight = sum(Decimal(str(hs_of(ln.desc)[1] or 0)) * ln.qty for ln in inv.lines)
        pk = max(1, int(weight / 25) + r.randrange(1, 4))
        blocks.append(("Expédition" if fr else "Shipment details", [
            ("Incoterm", "DAP Monaco – Quai Antoine Ier" if s.country != "Monaco" else "Livré à bord" if fr else "Delivered on board"),
            ("Transporteur" if fr else "Carrier", r.choice(["Riviera Express Fret", "TransAlp Logistics", "Méditerranée Messageries", "Own vehicle"])),
            ("N° de suivi" if fr else "Tracking no.", f"{r.choice(['RXF', 'TAL', 'MMS'])}{r.randrange(10**8, 10**9)}"),
            ("Colis" if fr else "Packages", f"{pk}"),
            ("Poids brut" if fr else "Gross weight", f"{fmt(weight * Decimal('1.08'), s.num)} kg"),
            ("Livraison" if fr else "Delivered", f"{fdate(dn.date, s.dstyle) if dn else fdate(inv.date, s.dstyle)}"
             + (f" – {dn.number}" if dn else ""))]))
        rows = []
        for k, ln in enumerate(inv.lines, 1):
            code, kg = hs_of(ln.desc)
            if code:
                rows.append([str(k), ln.sku or "—", code, _country(s) if s.country != "Monaco" else "FR",
                             fmt(Decimal(str(kg)) * ln.qty, s.num) + " kg"])
        blocks.append(("Données douanières par ligne" if fr else "Customs and Intrastat data per line",
                       T([("#", 10 * mm, "c"), ("Item" if not fr else "Réf.", 34 * mm, "l"), ("HS code" if not fr else "Code NC", 34 * mm, "l"),
                          ("Origin" if not fr else "Origine", 26 * mm, "c"), ("Net weight" if not fr else "Poids net", 34 * mm, "r")], rows)))
    else:
        dd = dn.date if dn else inv.date
        blocks.append(("Intervention" if fr else "Service details", [
            ("Lieu" if fr else "Location", "Port Hercule, Monaco – Quai Antoine Ier"),
            ("Date de réalisation" if fr else "Completed on", fdate(dd, s.dstyle)),
            ("Rapport" if fr else "Report", dn.number if dn else ("—" if fr else "—")),
            ("Intervenant" if fr else "Engineer in charge", r.choice(["J. Lemaire", "A. Rossi", "M. Dupuis", "K. Novak", "S. Ortega"])),
            ("Moyens" if fr else "Means", r.choice(["Fourgon atelier + outillage", "Service van and tools", "Atelier mobile"]))]))
    notes = (["Toute réclamation doit nous parvenir sous 8 jours à réception.", "Certifié ISO 9001:2015 – certificat n° "
              f"FR{r.randrange(10000, 99999)}-Q.", "Interlocuteur : service clients, " + s.phone + "."] if fr else
             ["Claims must be notified within 8 days of receipt.", f"ISO 9001:2015 certified – certificate no. {r.randrange(10000, 99999)}-Q.",
              "Customer service: " + s.phone + " – " + s.email + "."])
    blocks.append(("Notes", notes))
    return blocks


# ---------------------------------------------------------------- invoice annexes
def packing_list(inv, w):
    s, r = inv.s, _rnd("pk", inv.number)
    fr = s.lang == "fr"
    rows = []
    for k, ln in enumerate(inv.lines, 1):
        code, kg = hs_of(ln.desc)
        if not code:
            continue
        n = int(min(ln.qty, 12)) or 1
        per = ln.qty / n
        for j in range(n):
            rows.append([f"{k}.{j + 1}", ln.sku or "—", ln.desc[:46], f"{per.normalize():f}".replace(".", "," if fr else "."),
                         f"L{inv.date:%y%m}{r.randrange(1000, 9999)}", f"{r.choice(['SN', 'B'])}{r.randrange(10**6, 10**7)}",
                         fdate(inv.date + dt.timedelta(days=r.randrange(400, 1500)), "slash") if code[:2] in ("27", "32", "38", "36", "34", "85") else "—"])
    cert = [[f"{k}", ln.desc[:60], r.choice(["Declaration of conformity", "Material certificate 3.1", "MED wheelmark certificate",
                                            "Safety data sheet", "Type approval"]), f"DOC-{r.randrange(10000, 99999)}"]
            for k, ln in enumerate(inv.lines, 1) if hs_of(ln.desc)[0]]
    return [("Liste de colisage et traçabilité" if fr else "Packing list and traceability", [
                ("Détail des lots et numéros de série expédiés. " if fr else "Lots and serial numbers shipped. ")
                + (f"Bon de livraison {inv.dn}." if inv.dn and fr else f"Delivery note {inv.dn}." if inv.dn else ""),
                T([("Ligne" if fr else "Line", 14 * mm, "l"), ("Réf." if fr else "Item", 24 * mm, "l"), ("Désignation" if fr else "Description", 62 * mm, "l"),
                   ("Qté" if fr else "Qty", 12 * mm, "r"), ("Lot", 22 * mm, "l"), ("Série" if fr else "Serial/batch", 22 * mm, "l"),
                   ("Péremption" if fr else "Expiry", 20 * mm, "l")], rows)]),
            ("Certificats et documents fournis" if fr else "Certificates and documents supplied", [
                T([("#", 10 * mm, "c"), ("Article" if fr else "Item", 80 * mm, "l"), ("Document", 50 * mm, "l"), ("Référence" if fr else "Reference", 32 * mm, "l")], cert),
                "Les certificats sont disponibles sur demande et joints à la livraison." if fr else
                "Certificates accompany the delivery and are available on request in electronic form."])]


def timesheet(inv, w):
    s, r = inv.s, _rnd("ts", inv.number)
    fr = s.lang == "fr"
    dn = w.dn(inv.dn) if inv.dn else None
    end = dn.date if dn else inv.date
    techs = r.sample(["J. Lemaire", "A. Rossi", "M. Dupuis", "K. Novak", "S. Ortega", "P. Garnier", "L. Bruno"], 3)
    tasks_fr = ["Consignation et mise en sécurité", "Dépose de l'équipement existant", "Contrôle et mesures", "Pose et raccordement",
                "Essais fonctionnels", "Nettoyage et repli de chantier", "Réunion avec le chef mécanicien", "Rédaction du rapport"]
    tasks_en = ["Isolation and lock-out", "Removal of existing equipment", "Inspection and measurements", "Installation and connection",
                "Functional tests", "Cleaning and demobilisation", "Meeting with the Chief Engineer", "Report writing"]
    tasks = tasks_fr if fr else tasks_en
    hours = sum((ln.qty for ln in inv.lines if ln.unit in ("h",)), Decimal(0))
    days = max(2, min(6, int(hours / 8) + 1)) if hours else 3
    rows = []
    for k in range(days):
        d = end - dt.timedelta(days=days - 1 - k)
        for t in techs[:2 if k % 2 else 3]:
            rows.append([fdate(d, s.dstyle), t, tasks[(k * 3 + len(rows)) % len(tasks)], f"{r.choice([2, 3, 3.5, 4, 4.5])}".replace(".", "," if fr else "."),
                         r.choice(["Salle des machines", "Pont principal", "Local technique"] if fr else ["Engine room", "Main deck", "Technical space"])])
    mats = [[f"{k}", m, f"{r.randrange(1, 12)}", r.choice(["u", "m", "lot"])] for k, m in enumerate(
        (["Cosses et manchons", "Câble 2,5 mm²", "Gaine thermorétractable", "Colliers inox", "Visserie inox A4", "Joint silicone marine",
          "Ruban isolant", "Étiquettes de repérage"] if fr else
         ["Cable lugs", "Cable 2.5 mm2", "Heat-shrink sleeve", "Stainless clamps", "A4 stainless fasteners", "Marine sealant",
          "Insulating tape", "Marking labels"]), 1)]
    return [("Feuille de temps" if fr else "Timesheet", [
                ("Heures passées par intervenant ; les heures facturées figurent en page 1." if fr else
                 "Hours spent per engineer; the hours invoiced are shown on page 1."),
                T([("Date", 24 * mm, "l"), ("Intervenant" if fr else "Engineer", 32 * mm, "l"), ("Tâche" if fr else "Task", 70 * mm, "l"),
                   ("Heures" if fr else "Hours", 18 * mm, "r"), ("Zone", 30 * mm, "l")], rows)]),
            ("Fournitures consommées (incluses)" if fr else "Consumables used (included)", [
                T([("#", 10 * mm, "c"), ("Article" if fr else "Item", 100 * mm, "l"), ("Qté" if fr else "Qty", 20 * mm, "r"), ("U", 20 * mm, "c")], mats)]),
            ("Compte rendu" if fr else "Work report", [
                ("L'intervention a été réalisée conformément au bon de commande. Les essais en fonctionnement ont été réalisés en "
                 "présence de l'équipage et se sont révélés satisfaisants. Aucune réserve n'a été émise à la réception des travaux."
                 if fr else "The work was carried out in accordance with the purchase order. Functional tests were performed in "
                 "the presence of the crew and found satisfactory. No reservation was made at acceptance of the work."),
                ("Recommandation : contrôle préventif à prévoir dans 12 mois." if fr else
                 "Recommendation: preventive inspection in 12 months.")])]


def bunker_detail(inv, w):
    r = _rnd("bk", inv.number)
    litres = inv.lines[0].qty
    rows, cum = [], Decimal(0)
    step = Decimal(1000)
    t0 = dt.datetime.combine(w.dn(inv.dn).date, dt.time(7, 30))
    while cum < litres:
        q = min(step, litres - cum)
        cum += q
        rows.append([f"{t0:%H:%M}", f"{int(cum - q):,}", f"{int(cum):,}", f"{int(q):,}", f"{r.uniform(17.5, 21.5):.1f} °C",
                     f"{r.uniform(0.842, 0.848):.4f}"])
        t0 += dt.timedelta(minutes=r.randrange(5, 9))
    return [("Bunker delivery details", [
        f"Product: marine gasoil DMA (ISO 8217:2017), sulphur content max 0.10% m/m. Delivered by road tanker "
        f"{r.choice(['MC-4521-T', 'MC-7712-T'])} under bunker delivery note {inv.dn}.",
        T([("Time", 18 * mm, "l"), ("Meter start (L)", 32 * mm, "r"), ("Meter end (L)", 32 * mm, "r"), ("Delivered (L)", 30 * mm, "r"),
           ("Temp.", 22 * mm, "r"), ("Density 15 °C", 32 * mm, "r")], rows),
        T([("Parameter", 60 * mm, "l"), ("Result", 40 * mm, "r"), ("Limit ISO 8217", 40 * mm, "r")], [
            ["Density at 15 °C (kg/m3)", f"{r.uniform(842, 848):.1f}", "max 890.0"], ["Viscosity at 40 °C (mm2/s)", f"{r.uniform(2.6, 3.4):.2f}", "2.000-6.000"],
            ["Sulphur (% m/m)", f"{r.uniform(0.04, 0.09):.3f}", "max 0.100"], ["Flash point (°C)", f"{r.randrange(62, 70)}", "min 60"],
            ["Water (% v/v)", "< 0.05", "max 0.30"], ["Cloud point (°C)", f"{r.randrange(-6, -1)}", "report"]]),
        "Samples: 4 sealed samples drawn continuously at the vessel's manifold (seals "
        f"{r.randrange(100000, 999999)} to {r.randrange(100000, 999999)}); one retained on board for 12 months (MARPOL Annex VI, "
        "regulation 18).", "Supplier's declaration: the fuel oil supplied conforms with regulations 14 and 18 of MARPOL Annex VI."])]


def licence_schedule(inv, w):
    r = _rnd("lic", inv.number)
    rows = []
    for v in ("M/Y Aurelia", "M/Y Selene", "S/Y Blue Horizon"):
        rows.append([v, "ECDIS maintenance", f"ECM-{r.randrange(10000, 99999)}", "01/10/2026", "30/09/2027"])
        for area in ["Western Mediterranean", "Ligurian Sea", "Tyrrhenian Sea", "Adriatic", "Aegean", "Balearics", "Canaries",
                     "Caribbean – Leeward", "Caribbean – Windward", "Atlantic crossing"]:
            rows.append([v, f"Chart permits – {area}", f"AVCS-{r.randrange(100000, 999999)}", "01/10/2026", "30/09/2027"])
    return [("Licence schedule", ["Licences and chart permits covered by this invoice (period 01/10/2026 – 30/09/2027).",
             T([("Vessel", 32 * mm, "l"), ("Product", 62 * mm, "l"), ("Licence key", 32 * mm, "l"), ("From", 22 * mm, "l"), ("To", 22 * mm, "l")], rows)])]


def invoice_annex_for(inv, w):
    if inv.sup == "MFS":
        return bunker_detail(inv, w)
    if inv.sup == "NTS":
        return licence_schedule(inv, w)
    if is_goods(inv):
        return packing_list(inv, w)
    if inv.sup in ("SME", "NYS", "ECO", "MRS"):
        return timesheet(inv, w)
    return None


# ---------------------------------------------------------------- purchase orders
def po_allocation(po, sup):
    r = _rnd("po", po.number)
    cc = {"AURELIA": "VSL-AUR", "SELENE": "VSL-SEL", "BLUE": "VSL-BLH"}.get(po.vessel, "OFF-GEN")
    budget = (po.net * Decimal(r.uniform(3.2, 6.5))).quantize(Decimal("1"))
    used = (budget * Decimal(r.uniform(0.25, 0.7))).quantize(Decimal("1"))
    return [("Cost allocation", T([("Cost centre", 28 * mm, "l"), ("GL account", 26 * mm, "l"), ("Budget line", 56 * mm, "l"),
                                   ("Annual budget", 30 * mm, "r"), ("Committed YTD", 30 * mm, "r")],
                                  [[cc, sup.expense, f"{sup.activity}", fmt(budget), fmt(used)]])),
            ("Delivery instructions", [f"Deliver to {('the vessel' if cc.startswith('VSL') else 'the office')} at Quai Antoine Ier, "
                                       "Monaco, between 08:00 and 17:00 on business days. Announce the delivery 24 hours in advance "
                                       "to the Operations desk (+377 97 70 41 10). Each delivery must be accompanied by a delivery "
                                       "note quoting this purchase order number; the delivery note is signed on board.",
                                       "Quality: goods must be new, in original packaging, with certificates where applicable."])]


SUPPLIER_REQUIREMENTS = [
    ("Supplier requirements on board", [
        "Contractors working on board comply with the vessel's safety management system and the instructions of the Master. "
        "Before starting work, each technician attends a safety briefing given by the duty officer.",
        T([("Topic", 50 * mm, "l"), ("Requirement", 124 * mm, "l")], [
            ["Access", "Names of technicians sent 24 h in advance; identity document on boarding"],
            ["PPE", "Safety shoes, gloves and eye protection; harness for work at height"],
            ["Hot work", "Hot-work permit issued by the Chief Engineer; fire watch during and 30 min after"],
            ["Enclosed spaces", "Entry permit, gas measurement and attendant at the entrance"],
            ["Electrical work", "Lock-out / tag-out of circuits; verification of absence of voltage"],
            ["Waste", "Removed by the contractor; no disposal on board or in the harbour"],
            ["Environment", "Absorbent material available for any oil-related work"],
            ["Photographs", "Prohibited on board without the Master's consent"],
            ["Confidentiality", "No disclosure of the vessel's name, owner or itinerary"],
            ["Documents", "Delivery note or service report signed on board; certificates attached"]]),
        "Non-compliance with these requirements may lead to the immediate suspension of the work at the contractor's cost."])]

GPC_MORE = [
    ("11. Inspection and acceptance", "Acceptance of goods on board does not waive the company's right to reject goods found "
     "defective within 30 days of delivery. Rejected goods are collected at the supplier's cost."),
    ("12. Delay", "If the delivery date is not met, the company may cancel the order without compensation after a formal notice "
     "of 8 days, or apply a penalty of 0.5% of the order value per day of delay, capped at 10%."),
    ("13. Intellectual property", "The supplier warrants that the goods do not infringe any third-party right and indemnifies "
     "the company against any claim."),
    ("14. Insurance", "The supplier maintains public and product liability insurance with a reputable insurer for at least EUR "
     "2 million per claim and provides a certificate on request."),
    ("15. Subcontracting", "Subcontracting of works on board requires the company's prior written consent."),
    ("16. Health and safety", "Work on board is subject to the supplier requirements printed on the following page."),
    ("17. Data protection", "Personal data exchanged under the order are processed in accordance with Monegasque Law No. 1.565 and "
     "Regulation (EU) 2016/679."),
    ("18. Assignment", "The supplier may not assign receivables arising from the order without the company's written consent."),
]


# ---------------------------------------------------------------- delivery notes and payment notices
def dn_blocks(dn, sup):
    r = _rnd("dn", dn.number)
    fr = sup.lang == "fr"
    n = max(1, len(dn.items) + r.randrange(0, 3))
    packs = [[f"{k}", r.choice(["Carton", "Palette", "Fût", "Caisse"] if fr else ["Carton", "Pallet", "Drum", "Crate"]),
              f"{r.randrange(30, 120)}x{r.randrange(30, 90)}x{r.randrange(20, 80)} cm", f"{r.uniform(3, 180):.1f} kg"] for k in range(1, n + 1)]
    return [("Colisage" if fr else "Packages", T([("#", 10 * mm, "c"), ("Type", 40 * mm, "l"), ("Dimensions", 50 * mm, "l"),
                                                   ("Poids" if fr else "Weight", 30 * mm, "r")], packs)),
            ("Transport", [("Transporteur" if fr else "Carrier", r.choice(["Riviera Express Fret", "TransAlp Logistics", "Own vehicle"])),
                           ("Véhicule" if fr else "Vehicle", f"{r.choice(['MC', 'FR', 'IT'])}-{r.randrange(100, 999)}-{r.choice(['AB', 'KZ', 'TR'])}"),
                           ("Arrivée à quai" if fr else "Arrival on quay", f"{r.randrange(8, 16):02d}:{r.choice(['05', '20', '35', '50'])}"),
                           ("Contrôle" if fr else "Check", "Quantités comptées à bord" if fr else "Quantities counted on board")]),
            ("Conditions" if fr else "Conditions", [
                "Les réserves doivent être portées sur le présent document et confirmées par écrit sous 48 heures." if fr else
                "Any reservation must be written on this document and confirmed in writing within 48 hours.",
                "Marchandises voyageant aux risques du destinataire après signature." if fr else
                "Goods travel at the consignee's risk after signature."])]


def batch_details(payments):
    rows = []
    for k, p in enumerate(payments, 1):
        rows.append([str(k), f"E2E-{p.date:%y%m%d}-{hashlib.sha1(p.label.encode()).hexdigest()[:8].upper()}", "SHA",
                     "SUPP" if p.settles else "OTHR", f"{p.date:%d/%m/%Y} 07:{10 + k:02d}", "ACSC"])
    return rows


def lmp_detail(inv):
    """Detailed delivery list of a provisions invoice: items whose amounts add up exactly to each invoiced lot."""
    r = _rnd("lmp", inv.number)
    cat = {"Fruits et légumes frais": ["Tomates grappe", "Salade batavia", "Citrons de Menton", "Avocats", "Fraises", "Courgettes",
                                       "Herbes fraîches (botte)", "Mangues", "Pommes de terre grenaille"],
           "Viandes et poissons": ["Filet de bœuf", "Suprêmes de volaille", "Loup de Méditerranée", "Gambas", "Carré d'agneau",
                                   "Saumon label rouge", "Jambon cru", "Saint-Pierre"],
           "Épicerie fine et produits secs": ["Huile d'olive AOP", "Riz arborio", "Pâtes artisanales", "Chocolat 70 %", "Farine T55",
                                              "Miel de lavande", "Thé et infusions", "Café en grains"],
           "Vins et spiritueux": ["Champagne brut", "Côtes de Provence rosé", "Bordeaux rouge", "Gin premium", "Vodka", "Rhum vieux"],
           "Eaux minérales et boissons sans alcool": ["Eau plate 1 L", "Eau gazeuse 1 L", "Jus d'orange frais", "Sodas assortis", "Tonic"]}
    rows = []
    for ln in inv.lines:
        names = r.sample(cat[ln.desc], min(len(cat[ln.desc]), r.randrange(4, 7)))
        total, left = ln.amount, ln.amount
        for k, nm in enumerate(names):
            amt = left if k == len(names) - 1 else (total * Decimal(r.uniform(0.1, 0.3))).quantize(Decimal("0.01"))
            if amt >= left:
                amt = left
            left -= amt
            rows.append([ln.desc, nm, fmt(amt, "fr")])
            if left <= 0:
                break
    return [("Détail de la livraison", ["Détail des articles livrés à bord ; les montants HT par famille correspondent aux "
             "lignes de la facture.", T([("Famille", 62 * mm, "l"), ("Article", 80 * mm, "l"), ("Montant HT", 32 * mm, "r")], rows)])]


def berth_detail(inv):
    r = _rnd("mbm", inv.number)
    d0 = inv.date
    rows = []
    for k in range(0, 28, 1):
        d = d0 + dt.timedelta(days=k)
        if d.month != d0.month:
            break
        rows.append([fdate(d), "Occupied", f"{r.randrange(180, 420)} kWh", f"{r.uniform(1.5, 6.0):.1f} m3", r.choice(["—", "—", "Pump-out", "—"])])
    return [("Berth occupancy and meter readings", ["Daily occupancy record of the berth. Electricity and water are invoiced "
             "separately on meter readings, in accordance with the berth rental agreement.",
             T([("Date", 28 * mm, "l"), ("Status", 28 * mm, "l"), ("Electricity", 34 * mm, "r"), ("Water", 30 * mm, "r"),
                ("Services", 50 * mm, "l")], rows)])]
