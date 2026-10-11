"""Long contracts and accounting documents of AccountingBench (6-12 pages each, coherent with world.py).

Contracts are assembled from a clause library (common boilerplate + clauses specific to each contract), with
schedules as tables. Accounting documents (trial balance, bank reconciliation, budget, closing manual, AGM minutes)
take their figures from the world model where one exists, so no document contradicts another.
Nothing here provides for a payment schedule, a split between vessels or a prepayment that a question relies on.
"""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from reportlab.lib.units import mm

from common import D, date, fdate, fmt


def T(cols, rows):
    return ("table", cols, rows)


COMMON = [
    ("Definitions and interpretation", [
        "In this Agreement, unless the context otherwise requires: \"Agreement\" means this agreement and its schedules; "
        "\"Business Day\" means a day other than a Saturday, Sunday or public holiday in the Principality of Monaco; "
        "\"Confidential Information\" means any information disclosed by one party to the other in connection with this "
        "Agreement, whether before or after its signature; \"Vessel\" means any yacht under the management of {customer} "
        "for which Services or Goods are ordered under this Agreement.",
        "Headings are for convenience only. References to clauses and schedules are to clauses of and schedules to this "
        "Agreement. Words in the singular include the plural and vice versa. Where there is a conflict between the body of "
        "this Agreement and a schedule, the body of this Agreement prevails."]),
    ("Term", "This Agreement takes effect on {start} and continues for an initial period of {term}. It is then renewed "
     "automatically for successive periods of twelve months unless either party gives written notice of non-renewal at "
     "least three months before the end of the current period."),
    ("Orders and documentation", [
        "Each supply under this Agreement is the subject of a purchase order issued by {customer} in accordance with its "
        "procurement policy PRC-FIN-04, except where this Agreement expressly provides otherwise. A purchase order quotes "
        "the vessel, the quantities, the prices and the delivery date.",
        "Each delivery is accompanied by a delivery note, and each service by a service report, signed on board by the "
        "Master, the Chief Engineer or their delegate. Only the quantities recorded as received on the delivery note may be "
        "invoiced."]),
    ("Invoicing", [
        "{supplier} issues one invoice per purchase order or per delivery, addressed to accounts.payable@azurmarine.example, "
        "stating the purchase order number, the delivery note or service report number, the vessel, and every mention "
        "required by the applicable VAT legislation.",
        "Invoices that do not comply with this clause are returned and are not considered received for the purpose of "
        "calculating the payment term."]),
    ("Payment", "{payment}"),
    ("Bank details", "Payments are made exclusively to the bank account stated in Schedule 2. Any change of bank details "
     "is notified by a letter signed by an authorised representative of {supplier} and is effective only after "
     "confirmation by telephone by {customer} on the number stated in Schedule 2. {customer} is not liable for any "
     "payment made in good faith to the account stated in Schedule 2."),
    ("Warranties", [
        "{supplier} warrants that it holds all licences and approvals required to perform this Agreement, that its personnel "
        "are qualified and that the Goods and Services comply with the applicable flag, class and international "
        "requirements, including SOLAS and MARPOL where relevant.",
        "{supplier} remedies at its own cost any defect notified within twelve months of delivery or completion."]),
    ("Liability", "Except in the case of fraud, gross negligence, wilful misconduct, death or personal injury, the aggregate "
     "liability of each party under this Agreement in any contract year is limited to the total amount invoiced under this "
     "Agreement during the previous twelve months. Neither party is liable for loss of profit, loss of charter, loss of use "
     "of a vessel or any indirect loss."),
    ("Insurance", "{supplier} maintains, with reputable insurers, public and product liability insurance with a limit of not "
     "less than EUR 2,000,000 per occurrence, and employer's liability insurance as required by law, and provides "
     "certificates on request."),
    ("Confidentiality", "Each party keeps the other party's Confidential Information confidential and uses it only for the "
     "purpose of this Agreement. Information on the vessels, their owners, guests, itineraries and crew is Confidential "
     "Information. This obligation survives termination for five years."),
    ("Data protection", "Each party processes personal data received under this Agreement in accordance with Monegasque "
     "Law No. 1.565 of 3 December 2024 on the protection of personal data and, where applicable, Regulation (EU) 2016/679, "
     "only for the purpose of this Agreement and with appropriate security measures."),
    ("Anti-bribery and sanctions", "Each party complies with applicable anti-corruption laws and with the sanctions regimes "
     "of the Principality of Monaco, the United Nations and the European Union. Breach of this clause is a material breach."),
    ("Subcontracting", "{supplier} may not subcontract all or part of its obligations without the prior written consent of "
     "{customer}, and remains liable for its subcontractors."),
    ("Audit", "{customer} and its auditors may, on fifteen Business Days' notice and no more than once a year, audit the "
     "records of {supplier} relating to the prices and quantities invoiced under this Agreement."),
    ("Force majeure", "Neither party is liable for a failure caused by an event beyond its reasonable control, provided it "
     "notifies the other party promptly and uses reasonable efforts to mitigate its effects. If the event lasts more than "
     "sixty days, either party may terminate this Agreement by written notice."),
    ("Termination", [
        "Either party may terminate this Agreement by written notice with immediate effect if the other party commits a "
        "material breach that is not remedied within thirty days of a notice requiring it to do so, or becomes insolvent.",
        "Termination does not affect accrued rights. Purchase orders issued before termination are completed under the "
        "terms of this Agreement unless {customer} cancels them in writing."]),
    ("Notices", "Notices are given in writing to the addresses stated in Schedule 2, by registered letter or by e-mail with "
     "confirmation of receipt. Operational communications may be made by e-mail between the contacts listed in Schedule 2."),
    ("Assignment", "Neither party may assign this Agreement without the prior written consent of the other, except that "
     "{customer} may assign it to an entity of the Azur Yachting group."),
    ("Entire agreement, variation and waiver", "This Agreement constitutes the entire agreement between the parties on its "
     "subject matter. It may be varied only in writing signed by both parties. A failure to exercise a right is not a "
     "waiver of that right."),
    ("Governing law and jurisdiction", "This Agreement is governed by Monegasque law. The courts of the Principality of "
     "Monaco have exclusive jurisdiction, after an attempt at amicable settlement of thirty days."),
]


def contract(code, title, supplier, customer, start, term, recitals, specific, payment, schedules, signatories):
    fill = dict(supplier=supplier, customer=customer, start=fdate(start), term=term, payment=payment)

    def f(x):
        return [y.format(**fill) for y in x] if isinstance(x, list) else x.format(**fill)
    out = [("Parties", f"{supplier} and {customer} (together the \"parties\")."),
           ("Recitals", recitals)]
    n = 0
    for head, body in specific + COMMON:
        n += 1
        out.append((f"{n}. {head}", f(body) if not (isinstance(body, tuple)) else body))
    out += schedules
    out.append(("Signatures", T([("Party", 60 * mm, "l"), ("Name and function", 80 * mm, "l"), ("Date", 30 * mm, "l")],
                                signatories)))
    return out


def _contacts(rows):
    return T([("Party", 45 * mm, "l"), ("Contact", 50 * mm, "l"), ("Telephone", 35 * mm, "l"), ("E-mail", 44 * mm, "l")], rows)


AMS = "Azur Marine Services S.A.M."
AMS_SIG = ["Azur Marine Services S.A.M.", "Philippe Andrieu, Chief Executive Officer"]


def management_agreement(vessel, owner, owner_addr, fee_net, start, crew):
    fee_gross = (fee_net * Decimal("1.20")).quantize(Decimal("0.01"))
    budget = [[c, fmt(D(v))] for c, v in [("Crew wages and benefits", crew * 7200), ("Fuel and lubricants", 410000),
              ("Maintenance and repairs", 520000), ("Berth and marina", 57600 if "Aurelia" in vessel else 46800),
              ("Insurance (hull & machinery, P&I)", 52000), ("Provisions and guest supplies", 180000),
              ("Communications and IT", 36000), ("Safety and certification", 44000), ("Management fee (net of VAT)", int(fee_net * 12))]]
    return contract(
        f"MA-{vessel[4:7].upper()}", f"Yacht management agreement – {vessel}", AMS, owner, start, "three years",
        [f"{owner}, registered at {owner_addr}, owns the motor yacht {vessel} and wishes to entrust its technical, crew and "
         "financial management to a professional manager.", "Azur Marine Services S.A.M. is a yacht management company "
         "established in Monaco, holding the professional approvals required for that activity."],
        [("Appointment", ["The Owner appoints the Manager to manage the Vessel on its behalf, as agent, in accordance with this "
          "Agreement and with the Owner's instructions. The Manager accepts the appointment and undertakes to act with the "
          "diligence of a prudent professional manager.", "The Manager acts in the name and for the account of the Owner. "
          "Contracts concluded by the Manager for the Vessel are concluded on behalf of the Owner; the Manager is not "
          "personally liable for their performance."]),
         ("Technical management", ["The Manager organises the maintenance of the Vessel, the class and flag surveys, the "
          "yard periods and the repairs, selects the suppliers and contractors in accordance with its procurement policy, "
          "and supervises the works.", "Any single expense above EUR 15,000.00 excluding VAT requires the prior written "
          "approval of the Owner, except in an emergency affecting safety, in which case the Owner is informed within 24 "
          "hours."]),
         ("Crew management", [f"The Manager recruits, employs or contracts and administers a crew of {crew} persons, "
          "manages their rotations, payroll, social security and training, and ensures compliance with the Maritime Labour "
          "Convention 2006.", "Crew wages are paid by the Manager out of the funds provided by the Owner and recharged at "
          "cost."]),
         ("Financial management", ["The Manager keeps separate accounts for the Vessel, pays the Vessel's suppliers, and "
          "reports monthly to the Owner: budget versus actual, cash position, commitments, crew changes and technical "
          "status.", "Third-party costs are recharged to the Owner at cost, without mark-up, with copies of the supporting "
          "invoices. The Owner funds the operating account monthly in advance on the basis of the approved budget."]),
         ("Management fee", [f"The Owner pays the Manager a fixed management fee of EUR {fmt(fee_net)} per month excluding VAT "
          f"(EUR {fmt(fee_gross)} including VAT at 20%), invoiced on the first day of each month and payable within 15 "
          "days.", "The fee is reviewed annually on 1 January in line with the Monaco consumer price index."]),
         ("Budget", "The Manager submits an annual operating budget before 30 November of each year for approval by the "
          "Owner. The approved budget for 2026 is set out in Schedule 1.")],
        "Invoices of the Manager are payable within 15 days by bank transfer to the Manager's account with Banque Riviera "
        "Monaco. Recharges of third-party costs are payable on presentation of the monthly statement.",
        [("Schedule 1 – Approved operating budget 2026 (EUR)", T([("Item", 110 * mm, "l"), ("Budget 2026", 50 * mm, "r")], budget)),
         ("Schedule 2 – Contacts and bank details", [_contacts([
             ["Manager", "Philippe Andrieu (CEO)", "+377 97 70 41 00", "p.andrieu@azurmarine.example"],
             ["Manager – finance", "Claire Martin (Finance Director)", "+377 97 70 41 02", "c.martin@azurmarine.example"],
             ["Owner", "Owner's office", "+1 345 949 7700", "office@" + owner.split()[0].lower() + "-yachting.example"]]),
             "Manager's bank account: Banque Riviera Monaco, IBAN MC78 1273 9000 0100 0215 4876 318, BIC BRMCMCMXXXX."])],
        [AMS_SIG + [fdate(start)], [owner, "Director", fdate(start)]])


def supply_agreement(kind, supplier, sup_name, start, extra_specific, prices, payment, contacts, sig):
    return contract(f"FA-{supplier}", f"Framework {kind} agreement – {sup_name}", sup_name, AMS, start, "two years",
                    [f"{AMS} manages yachts based in Monaco and purchases {kind.lower()} for them on a regular basis.",
                     f"{sup_name} supplies {kind.lower()} to yachts in the Monaco area and wishes to be a listed supplier."],
                    extra_specific, payment,
                    [("Schedule 1 – Prices", T([("Item", 100 * mm, "l"), ("Unit", 30 * mm, "c"), ("Price EUR excl. VAT", 40 * mm, "r")], prices)),
                     ("Schedule 2 – Contacts and bank details", [_contacts(contacts[0]), contacts[1]])],
                    [sig, AMS_SIG[:1] + ["Claire Martin, Finance Director", fdate(start)]])


def all_contracts(SUPPLIERS):
    med, mfs, crw, lib, rtl, acs = (SUPPLIERS[k] for k in ("MED", "MFS", "CRW", "LIB", "RTL", "ACS"))
    out = {}
    out["mgmt_aurelia"] = ("Yacht management agreement – M/Y Aurelia", "en", date(2, 1, 2025), management_agreement(
        "M/Y Aurelia", "Aurelia Yachting Ltd", "Harbour Place, George Town, Grand Cayman", Decimal("40000.00"), date(2, 1, 2025), 14))
    out["mgmt_selene"] = ("Yacht management agreement – M/Y Selene", "en", date(1, 3, 2025), management_agreement(
        "M/Y Selene", "Selene Marine Holdings Ltd", "8 Ta' Xbiex Seafront, Malta", Decimal("26250.00"), date(1, 3, 2025), 9))
    out["fa_mediterra"] = ("Framework supply agreement – Mediterra Marine Supplies", "en", date(15, 12, 2025), supply_agreement(
        "Supply", "MED", med.name, date(15, 12, 2025),
        [("Scope", "Supply of engine-room consumables, lubricants, filters and spare parts to the vessels managed by Azur "
          "Marine Services, delivered on board in Monaco."),
         ("Prices", "Prices are those of Schedule 1, firm until 31 December 2026, then revised by agreement. Delivery and "
          "handling are invoiced EUR 320.00 per delivery in Monaco."),
         ("Delivery", "Orders placed before 12:00 are delivered within two Business Days. Partial deliveries are announced and "
          "documented by separate delivery notes.")],
        [["Lube oil SAE 15W-40, 208 L drum", "drum", "742.00"], ["Hydraulic oil ISO VG 46, 208 L drum", "drum", "698.00"],
         ["Fuel filter element FF-5320", "pc", "38.50"], ["Impeller kit for raw-water pump", "kit", "186.00"],
         ["Coolant concentrate, 20 L", "can", "64.50"], ["Oil absorbent pads (bale of 200)", "bale", "58.00"],
         ["Engine-room wipes (box of 500)", "box", "37.00"], ["Nitrile gloves (box of 100)", "box", "12.00"],
         ["Delivery and handling (Monaco)", "lot", "320.00"]],
        "Invoices are payable within 30 days of the invoice date by bank transfer. An invoice may be settled in two equal "
        "instalments within that period when the invoice so states.",
        ([["Supplier", "Billing department", med.phone, med.email], ["Customer", "Accounts Payable", "+377 97 70 41 05",
          "accounts.payable@azurmarine.example"]], f"Supplier's bank account: {med.bank}, IBAN {med.iban}, BIC {med.bic}."),
        [med.name, "Managing Director", fdate(date(15, 12, 2025))]))
    out["fa_marinafuel"] = ("Framework fuel supply agreement – Marina Fuel Services", "en", date(10, 1, 2026), supply_agreement(
        "Fuel supply", "MFS", mfs.name, date(10, 1, 2026),
        [("Scope", "Supply of marine gasoil (MGO, ISO 8217 DMA) by road tanker or barge to the vessels managed by Azur "
          "Marine Services in the port of Monaco."),
         ("Ordering and delivery", "Each bunkering is ordered by purchase order at least 48 hours in advance and delivered to "
          "one vessel. Quantities are measured by the tanker's calibrated meter and recorded on a bunker delivery note signed "
          "by the vessel's Chief Engineer, with a sealed sample retained on board."),
         ("Price", "The price per litre is the Riviera Bunker Index for the month of delivery plus the margin stated in "
          "Schedule 1. The price is stated on the purchase order.")],
        [["MGO DMA – truck delivery, margin over index", "litre", "0.012"], ["MGO DMA – barge delivery, margin over index", "litre", "0.006"],
         ["After-hours delivery surcharge", "delivery", "180.00"], ["Sampling and analysis (on request)", "sample", "95.00"]],
        "Each bunker delivery is invoiced separately and the invoice is payable in full within 30 days of the invoice date "
        "by bank transfer.",
        ([["Supplier", "Accounts", mfs.phone, mfs.email], ["Customer", "Operations desk", "+377 97 70 41 10",
          "operations@azurmarine.example"]], f"Supplier's bank account: {mfs.bank}, IBAN {mfs.iban}, BIC {mfs.bic}."),
        [mfs.name, "General Manager", fdate(date(10, 1, 2026))]))
    out["fa_crewlink"] = ("Crew management services agreement – CrewLink Maritime", "en", date(1, 4, 2024), supply_agreement(
        "Crew services", "CRW", crw.name, date(1, 4, 2024),
        [("Scope", "Recruitment, pre-employment checks, travel arrangements and visa processing of crew members for the vessels "
          "managed by Azur Marine Services."),
         ("Recruitment", "CrewLink presents at least two candidates per position, with verified certificates (STCW), "
          "references and medical fitness certificates (ENG1 or equivalent). A placement fee is due only when the candidate "
          "joins the vessel."),
         ("Replacement guarantee", "If a placed crew member leaves within 60 days of joining, CrewLink presents a replacement "
          "free of charge.")],
        [["Placement fee – deckhand / stewardess", "placement", "2,400.00"], ["Placement fee – officer / engineer", "placement", "3,600.00"],
         ["Travel arrangement and visa processing", "crew member", "462.50"], ["Background screening", "candidate", "150.00"]],
        "Invoices are payable within 30 days of the invoice date. VAT is accounted for by the customer under the "
        "reverse-charge mechanism.",
        ([["Supplier", "Finance", crw.phone, crw.email], ["Customer", "Crew department", "+377 97 70 41 12",
          "crew@azurmarine.example"]], f"Supplier's bank account: {crw.bank}, IBAN {crw.iban}, BIC {crw.bic}."),
        [crw.name, "Director", fdate(date(1, 4, 2024))]))
    out["fa_lighthouse"] = ("Insurance brokerage mandate – Lighthouse Insurance Brokers", "en", date(1, 12, 2023), supply_agreement(
        "Insurance brokerage", "LIB", lib.name, date(1, 12, 2023),
        [("Mandate", "Azur Marine Services, acting for the owners of the managed vessels, appoints Lighthouse Insurance Brokers "
          "as exclusive broker for hull & machinery, protection & indemnity and office insurance."),
         ("Placement and renewal", "The broker obtains at least three quotations at each renewal, presents a comparative "
          "report and places the covers chosen by the client. It reviews the adequacy of agreed values annually."),
         ("Claims handling", "The broker notifies claims to insurers, assists in the collection of documents and follows "
          "settlement until payment."),
         ("Remuneration", "The broker is remunerated by brokerage included in the premiums; no fee is invoiced to the client "
          "unless agreed in writing for a specific assignment.")],
        [["Brokerage on premiums (paid by insurers)", "% of premium", "10.0"], ["Specific consultancy (on request)", "hour", "180.00"]],
        "Premium debit notes are payable within 15 days to the broker's client account; premiums are exempt from VAT.",
        ([["Broker", "Premium accounts", lib.phone, lib.email], ["Client", "Finance Director", "+377 97 70 41 02",
          "c.martin@azurmarine.example"]], f"Broker's client account: {lib.bank}, IBAN {lib.iban}, BIC {lib.bic}."),
        [lib.name, "Managing Director", fdate(date(1, 12, 2023))]))
    out["fa_telecom"] = ("Business telecommunications contract – Riviera Telecom", "en", date(1, 2, 2025), supply_agreement(
        "Telecommunications", "RTL", rtl.name, date(1, 2, 2025),
        [("Services", "Fixed lines, fibre internet access 1 Gb/s with backup 4G link, and a fleet of 14 mobile lines with "
          "unlimited national and roaming bundles in the EU and the United Kingdom."),
         ("Service levels", "Fibre availability 99.9% per month; repair within 4 hours for a total outage, 1 Business Day for "
          "a degraded service. Service credits of 10% of the monthly fee per breach."),
         ("Equipment", "Routers and handsets remain the property of Riviera Telecom and are returned at the end of the contract.")],
        [["Fibre 1 Gb/s + 4G backup", "month", "389.00"], ["Fixed lines (6)", "month", "96.00"],
         ["Mobile line Pro Unlimited", "line / month", "41.81"], ["Out-of-bundle roaming outside the EU", "MB", "0.05"]],
        "Invoices are issued on the first day of each month and collected by SEPA direct debit on the 15th.",
        ([["Supplier", "Business customer care", rtl.phone, rtl.email], ["Customer", "Office manager", "+377 97 70 41 00",
          "office@azurmarine.example"]], f"Direct debit creditor: {rtl.name}, ICS MC12ZZZ000000384."),
        [rtl.name, "Head of Business Sales", fdate(date(1, 2, 2025))]))
    out["fa_cleaning"] = ("Contrat de prestation de nettoyage – Azure Clean Services", "fr", date(1, 9, 2021), [
        ("Parties", f"{acs.name} (le « Prestataire ») et {AMS} (le « Client »)."),
        ("1. Objet", "Nettoyage des bureaux du Client, 7 Quai Antoine Ier, 98000 Monaco (186 m²), cinq jours par semaine."),
        ("2. Prestations", T([("Prestation", 100 * mm, "l"), ("Fréquence", 70 * mm, "l")], [
            ["Vidage des corbeilles et tri sélectif", "Quotidienne"], ["Aspiration des sols et moquettes", "Quotidienne"],
            ["Nettoyage des sanitaires et de la kitchenette", "Quotidienne"], ["Dépoussiérage des bureaux", "Bihebdomadaire"],
            ["Lavage des sols durs", "Hebdomadaire"], ["Nettoyage des vitres intérieures", "Mensuelle"],
            ["Nettoyage des vitres extérieures", "Trimestrielle"], ["Shampooing des moquettes", "Annuelle"]])),
        ("3. Prix", "Forfait mensuel de 980,00 € HT, révisable chaque 1er septembre selon l'indice des prix des services de "
         "nettoyage. Les prestations supplémentaires font l'objet d'un devis."),
        ("4. Facturation et paiement", "Facture mensuelle émise le 25 du mois, payable à 30 jours par virement."),
        ("5. Personnel", "Le Prestataire emploie et encadre son personnel, qui respecte le règlement intérieur et la "
         "confidentialité des informations du Client. Il fournit les produits, le matériel et les consommables."),
        ("6. Assurances", "Le Prestataire est assuré en responsabilité civile professionnelle pour 1 500 000 € par sinistre."),
        ("7. Durée", "Un an à compter du 1er septembre 2021, renouvelable par tacite reconduction, résiliable avec un préavis "
         "de trois mois."),
        ("8. Droit applicable", "Droit monégasque ; tribunaux de Monaco."),
        ("Signatures", T([("Partie", 60 * mm, "l"), ("Nom et qualité", 80 * mm, "l"), ("Date", 30 * mm, "l")],
                         [[acs.name, "Gérante", "01/09/2021"], [AMS, "Philippe Andrieu, Administrateur délégué", "01/09/2021"]]))])
    return out


# ---------------------------------------------------------------- accounting documents
def bank_account_agreement():
    return [
        ("Article 1 – Objet", "La présente convention régit le fonctionnement du compte courant professionnel ouvert au nom "
         "d'Azur Marine Services S.A.M. dans les livres de la Banque Riviera Monaco, agence Monte-Carlo Moulins, ainsi que les "
         "services de paiement qui y sont associés."),
        ("Article 2 – Ouverture du compte", ["L'ouverture du compte est subordonnée à la remise des statuts, d'un extrait du "
         "Répertoire du Commerce et de l'Industrie de moins de trois mois, de la liste des bénéficiaires effectifs et des "
         "pièces d'identité des représentants légaux et des mandataires.", "Le client informe la banque sans délai de toute "
         "modification de ces informations."]),
        ("Article 3 – Mandataires et pouvoirs", T([("Mandataire", 60 * mm, "l"), ("Fonction", 50 * mm, "l"), ("Pouvoirs", 64 * mm, "l")], [
            ["Philippe Andrieu", "Administrateur délégué", "Tous pouvoirs, sans limite"],
            ["Claire Martin", "Directrice financière", "Validation des virements, sans limite"],
            ["Sofia Bianchi", "Comptable fournisseurs", "Saisie des ordres, sans pouvoir de validation"],
            ["Inès Morel", "Chef comptable", "Consultation, rapprochements"]])),
        ("Article 4 – Banque en ligne", ["L'accès à BRM Online Business se fait par identifiant, mot de passe et "
         "authentification forte sur l'application mobile de la banque. Les ordres de virement sont saisis par un utilisateur "
         "et validés par un autre utilisateur disposant du pouvoir de validation (double validation).", "Le client conserve "
         "ses dispositifs d'authentification sous sa garde exclusive et signale sans délai toute perte ou tout usage suspect."]),
        ("Article 5 – Virements SEPA", ["La banque exécute les virements SEPA sur la base de l'identifiant unique (IBAN) fourni "
         "par le client. Conformément à la réglementation, la banque n'est pas tenue de vérifier la concordance entre le nom "
         "du bénéficiaire et l'IBAN ; un virement exécuté conformément à l'IBAN indiqué est réputé correctement exécuté.",
         "Le client est seul responsable de l'exactitude des coordonnées bancaires qu'il saisit, notamment en cas de "
         "modification des coordonnées d'un fournisseur. La banque recommande la vérification par contre-appel de toute "
         "demande de changement de coordonnées reçue par courriel.", "En cas de virement frauduleux ou erroné, la banque "
         "s'efforce de récupérer les fonds sur demande du client, sans garantie de résultat."]),
        ("Article 6 – Prélèvements SEPA", "Le client peut s'opposer à un prélèvement ou en demander le remboursement dans les "
         "conditions légales. Les mandats de prélèvement sont conservés par les créanciers."),
        ("Article 7 – Relevés de compte", "Un relevé mensuel est mis à disposition dans l'espace de banque en ligne. Les "
         "réclamations relatives aux opérations doivent être formulées dans un délai de trente jours à compter de la mise à "
         "disposition du relevé."),
        ("Article 8 – Dates de valeur", "Les débits sont valorisés à la date de l'opération. Les crédits reçus par virement sont "
         "valorisés le premier jour ouvré suivant leur réception."),
        ("Article 9 – Tarification", T([("Service", 110 * mm, "l"), ("Tarif", 60 * mm, "r")], [
            ["Tenue de compte professionnel", "45,00 € / mois"], ["Abonnement BRM Online Business Pro", "18,00 € / mois"],
            ["Virement SEPA émis", "0,50 € / opération"], ["Virement international hors SEPA", "25,00 € / opération"],
            ["Prélèvement SEPA reçu", "gratuit"], ["Commission d'intervention", "8,00 € / opération, plafond 80,00 € / mois"],
            ["Recherche de virement (récupération de fonds)", "35,00 € / demande"]])),
        ("Article 10 – Découvert", "Aucune autorisation de découvert n'est consentie au titre de la présente convention."),
        ("Article 11 – Lutte contre le blanchiment", "La banque applique les obligations de vigilance de la loi n° 1.362 et peut "
         "demander tout justificatif sur l'origine ou la destination des fonds."),
        ("Article 12 – Secret bancaire et données personnelles", "La banque est tenue au secret professionnel. Les données "
         "personnelles sont traitées conformément à la loi n° 1.565."),
        ("Article 13 – Durée et résiliation", "Convention à durée indéterminée, résiliable par le client à tout moment et par la "
         "banque avec un préavis de deux mois."),
        ("Article 14 – Droit applicable", "Droit monégasque ; tribunaux de Monaco."),
        ("Signatures", T([("Partie", 60 * mm, "l"), ("Représentant", 80 * mm, "l"), ("Date", 30 * mm, "l")], [
            ["Banque Riviera Monaco", "Directeur d'agence", "12/01/2022"], ["Azur Marine Services S.A.M.", "Philippe Andrieu", "12/01/2022"]]))]


def trial_balance(w, ledger_balance, bank_balance_aug):
    """Balance générale au 31/08/2026: supplier accounts computed from the world, bank = August statement."""
    from world import SUPPLIERS
    at = date(31, 8)
    rows, tot_d, tot_c = [], D(0), D(0)

    def add(acc, name, debit=D(0), credit=D(0)):
        nonlocal tot_d, tot_c
        rows.append([acc, name, fmt(debit, "fr") if debit else "", fmt(credit, "fr") if credit else ""])
        tot_d += debit
        tot_c += credit
    fixed = [("201000", "Frais d'établissement et logiciels", D("18400.00")), ("213500", "Agencements et installations", D("142600.00")),
             ("218300", "Matériel informatique", D("38400.00")), ("218200", "Matériel de transport", D("31900.00")),
             ("275000", "Dépôts et cautionnements", D("24000.00"))]
    for a, n, v in fixed:
        add(a, n, debit=v)
    add("280000", "Amortissements des immobilisations", credit=D("103980.00"))
    add("101000", "Capital social", credit=D("450000.00"))
    add("106100", "Réserve légale", credit=D("45000.00"))
    add("110000", "Report à nouveau", credit=D("76000.00"))
    add("164000", "Emprunt PR-2025-0119", credit=D("126270.08"))
    ap_total = D(0)
    for code, s in sorted(SUPPLIERS.items(), key=lambda kv: kv[1].account):
        b = ledger_balance(w, code, at)
        if b:
            add(s.account, s.name, credit=b) if b > 0 else add(s.account, s.name, debit=-b)
            ap_total += b
    add("411000", "Clients – armateurs", debit=D("318420.00"))
    add("421000", "Personnel – rémunérations dues", credit=D("0.00"))
    add("431000", "Sécurité sociale", credit=D("31862.40"))
    add("445660", "TVA déductible", debit=D("27904.00"))
    add("445710", "TVA collectée", credit=D("42118.00"))
    add("512000", "Banque Riviera Monaco", debit=bank_balance_aug)
    pl = [("601000", "Achats refacturés", D("882000.00"), "D"), ("602200", "Fournitures et consommables", D("61240.00"), "D"),
          ("606100", "Carburant", D("52300.00"), "D"), ("613200", "Locations (anneaux)", D("69600.00"), "D"),
          ("615500", "Entretien et réparations navires", D("41870.00"), "D"), ("616000", "Assurances", D("39380.00"), "D"),
          ("621100", "Personnel extérieur", D("19650.00"), "D"), ("626000", "Télécommunications", D("10380.00"), "D"),
          ("641000", "Rémunérations du personnel", D("1406400.00"), "D"), ("645000", "Charges sociales", D("510600.00"), "D"),
          ("681100", "Dotations aux amortissements", D("25600.00"), "D"), ("706000", "Honoraires de gestion", D("2428000.00"), "C"),
          ("708000", "Refacturations aux armateurs", D("882000.00"), "C")]
    for a, n, v, side in pl:
        add(a, n, debit=v) if side == "D" else add(a, n, credit=v)
    diff = tot_d - tot_c
    add("467000", "Autres comptes débiteurs ou créditeurs", credit=diff) if diff > 0 else add("467000", "Autres comptes débiteurs ou créditeurs", debit=-diff)
    rows.append(["", "TOTAUX", fmt(tot_d, "fr"), fmt(tot_c, "fr")])
    return [("Balance générale au 31/08/2026", [
        "Balance des comptes généraux après clôture d'août 2026 (non auditée). Les comptes fournisseurs 401 sont repris du "
        "grand-livre auxiliaire ; le compte 512000 correspond au solde du relevé bancaire d'août.",
        T([("Compte", 25 * mm, "l"), ("Intitulé", 95 * mm, "l"), ("Débit", 27 * mm, "r"), ("Crédit", 27 * mm, "r")], rows)]),
        ("Contrôles", ["Total des débits égal au total des crédits.", f"Total des comptes fournisseurs (401) : "
         f"{fmt(ap_total, 'fr')} € créditeur, égal au total du grand-livre auxiliaire au 31/08/2026.",
         "Le compte d'attente 471000 est soldé au 31/08/2026."])]


def bank_reconciliation_aug(bank_balance_aug, book_balance):
    return [("Rapprochement bancaire – compte 512000 – 31/08/2026", [
        "Banque Riviera Monaco, compte n° 00021548763. Rapprochement préparé par Inès Morel le 03/09/2026, revu par Claire "
        "Martin le 04/09/2026.",
        T([("Libellé", 120 * mm, "l"), ("Montant EUR", 50 * mm, "r")], [
            ["Solde du relevé bancaire au 31/08/2026", fmt(bank_balance_aug, "fr")],
            ["+ Encaissements comptabilisés non crédités par la banque", "0,00"],
            ["– Paiements comptabilisés non débités par la banque", "0,00"],
            ["Solde rapproché", fmt(bank_balance_aug, "fr")], ["Solde comptable 512000 au 31/08/2026", fmt(book_balance, "fr")],
            ["Écart", fmt(bank_balance_aug - book_balance, "fr")]]),
        "Toutes les opérations du relevé d'août 2026 ont été pointées avec les écritures du journal de banque. Aucune "
        "opération non identifiée."]),
        ("Méthode", ["Pointage ligne à ligne du relevé avec le journal BQ ; contrôle de la séquence des numéros de relevé ; "
         "contrôle des virements émis avec les avis d'exécution de la banque ; contrôle des prélèvements avec les mandats.",
         "Toute opération non identifiée est enregistrée en compte d'attente 471000 et fait l'objet d'une recherche "
         "documentée avant la clôture suivante."])]


def closing_manual():
    steps = [
        ("J-2", "Relance des fournisseurs clés pour l'envoi des factures du mois", "Comptable fournisseurs"),
        ("J0", "Arrêté de la saisie des factures reçues jusqu'au dernier jour du mois", "Comptable fournisseurs"),
        ("J+1", "Édition du journal des achats et contrôle des doublons", "Comptable fournisseurs"),
        ("J+1", "Rapprochement bancaire et pointage des virements avec les avis d'exécution", "Chef comptable"),
        ("J+2", "Liste des livraisons et prestations du mois sans facture (bons de livraison, rapports)", "Opérations"),
        ("J+2", "Factures reçues après la clôture relatives au mois : liste des charges à payer", "Chef comptable"),
        ("J+3", "Rapprochement des relevés des fournisseurs clés", "Chef comptable"),
        ("J+3", "Revue de la balance âgée fournisseurs et des litiges", "Directrice financière"),
        ("J+4", "Revue du compte d'attente 471000", "Chef comptable"),
        ("J+4", "Registre des anomalies du mois", "Chef comptable"),
        ("J+5", "Validation de la clôture et reporting au CEO", "Directrice financière")]
    return [
        ("1. Objet", "Ce manuel décrit les travaux de clôture mensuelle du cycle achats-fournisseurs et trésorerie d'Azur "
         "Marine Services S.A.M. Il complète la procédure achats PRC-FIN-04."),
        ("2. Calendrier de clôture", T([("Jour", 18 * mm, "c"), ("Tâche", 110 * mm, "l"), ("Responsable", 46 * mm, "l")],
                                       [list(x) for x in steps])),
        ("3. Journal des achats", ["Seules les factures reçues au plus tard le dernier jour du mois sont saisies dans le journal "
         "du mois. Chaque facture reçoit un numéro de pièce AC-AAMM-NNN.", "Avant édition du journal, la comptable contrôle "
         "que le numéro de facture n'a pas déjà été saisi pour le même fournisseur. Les duplicata envoyés par les fournisseurs "
         "sont rapprochés de la facture d'origine et ne sont pas saisis."]),
        ("4. Rapprochement bancaire", "Chaque opération du relevé est rapprochée d'une pièce justificative : facture, avoir, "
         "bon de commande, bulletin de paie, déclaration fiscale ou sociale. Les débits sans justificatif sont portés en compte "
         "d'attente et signalés à la Directrice financière le jour même."),
        ("5. Rapprochements fournisseurs", "Les relevés de compte de Mediterra Marine Supplies, Oceanic Safety Europe et Côte "
         "d'Azur Ship Chandlers sont rapprochés chaque mois du grand-livre auxiliaire. Chaque écart est expliqué document par "
         "document."),
        ("6. Charges à payer (FNP)", ["Sont provisionnées : les factures reçues après la clôture relatives à des biens livrés ou "
         "à des prestations achevées dans le mois ; les biens ou prestations reçus sans facture, au prix du bon de commande.",
         "Le montant provisionné est le montant hors taxes. Chaque ligne de provision référence le bon de livraison ou le "
         "rapport d'intervention."]),
        ("7. Registre des anomalies", ["Le registre recense toutes les anomalies relevées pendant la clôture, avec leur type, "
         "le document concerné, le montant en jeu et l'action décidée. Une anomalie relevée lors d'un contrôle détaillé est "
         "obligatoirement reportée dans le registre de synthèse.", T([("Type", 80 * mm, "l"), ("Montant en jeu", 94 * mm, "l")], [
            ["Doublon de saisie", "Montant TTC de la facture"], ["Paiement partiel ou insuffisant", "Montant restant dû"],
            ["Paiement antérieur à la facture ou à la livraison", "Montant payé"], ["Facture sans bon de commande", "Montant TTC"],
            ["Bon de commande au-delà de la délégation", "Montant HT du bon"], ["Quantité facturée > livrée", "Excédent × prix unitaire HT"],
            ["Erreur de TVA", "Écart de TVA"], ["Facture non conforme", "Montant TTC"], ["IBAN différent du fichier", "Montant payé"],
            ["Débit bancaire non justifié", "Montant du débit"], ["Charge à payer", "Montant HT"]])]),
        ("8. Documentation", "Les états de clôture sont classés dans le dossier de clôture du mois : journal, grand-livre, "
         "balance âgée, rapprochements, liste des charges à payer, registre des anomalies, validation de la Directrice "
         "financière."),
        ("9. Contrôle de complétude", "La revue est complète lorsque chaque ligne du journal et chaque opération du relevé ont "
         "été examinées. Les documents introuvables sont listés nommément ; une revue partielle est signalée comme telle.")]


def budget_2026():
    rnd = random.Random(2026)
    out = []
    for vessel, scale in (("M/Y Aurelia", 1.0), ("M/Y Selene", 0.66), ("S/Y Blue Horizon", 0.42)):
        rows = []
        for item, base in [("Crew wages", 1008000), ("Crew travel and training", 64000), ("Fuel and lubricants", 410000),
                           ("Maintenance and repairs", 520000), ("Yard period", 300000), ("Berth and marina", 57600),
                           ("Insurance", 52000), ("Provisions", 180000), ("Communications and IT", 36000),
                           ("Safety and certification", 44000), ("Management fee", 480000)]:
            b = int(base * scale)
            q = [int(b * x) for x in (0.22, 0.31, 0.29)]
            q.append(b - sum(q))
            rows.append([item, fmt(D(b))] + [fmt(D(v)) for v in q])
        out.append((f"Budget 2026 – {vessel} (EUR)", T([("Item", 52 * mm, "l"), ("Year", 26 * mm, "r"), ("Q1", 24 * mm, "r"),
                                                         ("Q2", 24 * mm, "r"), ("Q3", 24 * mm, "r"), ("Q4", 24 * mm, "r")], rows)))
    return [("Introduction", "Operating budgets 2026 approved by the owners, prepared by Azur Marine Services S.A.M. in "
             "November 2025. Amounts excluding VAT. Quarterly phasing reflects the summer season and the winter yard periods.")] + out


def agm_minutes():
    return [
        ("Composition", "L'assemblée générale ordinaire des actionnaires d'Azur Marine Services S.A.M. s'est réunie le 25 juin "
         "2026 à 11 heures au siège social. Actionnaires présents ou représentés : 100 % du capital. Président de séance : "
         "Philippe Andrieu. Secrétaire : Claire Martin."),
        ("Ordre du jour", ["Rapport du conseil d'administration sur l'exercice 2025.", "Rapport des commissaires aux comptes.",
                           "Approbation des comptes de l'exercice clos le 31 décembre 2025.", "Affectation du résultat.",
                           "Quitus aux administrateurs.", "Questions diverses."]),
        ("Première résolution", "L'assemblée, après avoir entendu la lecture du rapport du conseil et du rapport des "
         "commissaires aux comptes, approuve les comptes de l'exercice 2025 tels qu'ils ont été présentés, faisant apparaître "
         "un bénéfice de 57 580 €. Adoptée à l'unanimité."),
        ("Deuxième résolution", "L'assemblée décide d'affecter le bénéfice de 57 580 € au report à nouveau. Adoptée à l'unanimité."),
        ("Troisième résolution", "L'assemblée donne quitus entier et sans réserve aux administrateurs pour leur gestion de "
         "l'exercice 2025. Adoptée à l'unanimité."),
        ("Quatrième résolution", "L'assemblée prend acte de la mise à jour de la procédure achats PRC-FIN-04 (version 3) et du "
         "suivi des recommandations de l'audit interne 2025. Adoptée à l'unanimité."),
        ("Clôture", "L'ordre du jour étant épuisé, la séance est levée à 12 h 15. Le présent procès-verbal est signé par le "
         "président et le secrétaire.")]
