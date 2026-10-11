"""Long-form content for the multi-page documents of AccountingBench.

Everything here is consistent with world.py (same company, people, vessels, suppliers and policy) and never states a
figure that an AccountingBench question asks about, so the long documents add reading load without adding answers.
"""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from reportlab.lib.units import mm

from common import D, fdate, fmt


def T(cols, rows):
    return ("table", cols, rows)


# ---------------------------------------------------------------- procurement policy: annexes
POLICY_MORE = [
    ("Annex C – From need to payment", [
        "The table below describes the purchase-to-pay process step by step. Each step produces a document that is filed "
        "in the document management system and can be traced from the purchase order number.",
        T([("#", 8 * mm, "c"), ("Step", 46 * mm, "l"), ("Actor", 34 * mm, "l"), ("Document", 42 * mm, "l"), ("Control", 40 * mm, "l")], [
            ["1", "Need expressed", "Master / Chief Engineer", "Purchase request (e-mail)", "Budget line exists"],
            ["2", "Quotations", "Operations", "Supplier quotations", "2 quotes above EUR 5,000"],
            ["3", "Purchase order", "Operations", "PO-YYYY-NNNN", "Approval matrix (section 3)"],
            ["4", "Order acknowledgement", "Supplier", "Acknowledgement e-mail", "Price and terms unchanged"],
            ["5", "Receipt of goods", "Bosun / Chief Engineer", "Signed delivery note", "Quantities counted"],
            ["6", "Completion of works", "Master / Chief Engineer", "Signed service report", "Date of completion"],
            ["7", "Invoice receipt", "Accounts Payable", "Supplier invoice", "Received stamp, date"],
            ["8", "Three-way match", "Accounts Payable", "PO + DN + invoice", "Quantities, prices, VAT"],
            ["9", "Booking", "Accounts Payable", "Purchase journal AC", "Not already booked"],
            ["10", "Payment proposal", "Accounts Payable", "Payment run list", "Due date, IBAN on file"],
            ["11", "Payment approval", "Finance Director", "Bank e-signature", "Segregation of duties"],
            ["12", "Execution", "Bank", "Payment execution notice", "Matches the run list"],
            ["13", "Bank reconciliation", "Chief Accountant", "Bank statement", "Every debit matched"],
            ["14", "Supplier reconciliation", "Chief Accountant", "Supplier statement", "Monthly for key suppliers"],
            ["15", "Month-end cut-off", "Chief Accountant", "Accrual schedule", "Section 7"]])]),
    ("Annex D – Responsibility matrix (RACI)", [
        "R = responsible, A = accountable, C = consulted, I = informed.",
        T([("Activity", 62 * mm, "l"), ("Requester", 22 * mm, "c"), ("Ops Mgr", 20 * mm, "c"), ("Fin. Dir.", 20 * mm, "c"),
           ("CEO", 16 * mm, "c"), ("AP", 16 * mm, "c"), ("Chief Acc.", 20 * mm, "c")], [
            ["Express a need", "R", "A", "I", "", "", ""], ["Select supplier", "C", "R", "C", "I", "", ""],
            ["Approve PO up to 5,000", "I", "A", "I", "", "", ""], ["Approve PO 5,000-20,000", "I", "R", "A", "I", "", ""],
            ["Approve PO above 20,000", "I", "R", "C", "A", "", ""], ["Receive goods", "R", "A", "", "", "I", ""],
            ["Book invoice", "", "C", "I", "", "R", "A"], ["Create supplier", "", "C", "A", "", "R", "I"],
            ["Change bank details", "", "", "A", "I", "R", "C"], ["Propose payments", "", "", "C", "", "R", "A"],
            ["Approve payments", "", "", "A", "I", "", "C"], ["Bank reconciliation", "", "", "A", "", "C", "R"],
            ["Cut-off and accruals", "", "C", "A", "", "C", "R"], ["Exception reporting", "", "I", "R", "A", "C", "C"]])]),
    ("Annex E – Change of supplier bank details", [
        "Fraudulent requests to change bank details are the most frequent attempt observed in the yachting sector. They "
        "usually arrive by e-mail from a domain that closely resembles the supplier's, shortly before a large payment, and "
        "insist on urgency or on the imminent closure of the previous account.",
        T([("#", 8 * mm, "c"), ("Action", 92 * mm, "l"), ("Who", 34 * mm, "l"), ("Evidence kept", 36 * mm, "l")], [
            ["1", "Receive the request in writing on the supplier's letterhead", "Accounts Payable", "Letter / PDF"],
            ["2", "Compare the sender's address with the master file contact", "Accounts Payable", "Screenshot"],
            ["3", "Call back the supplier on the number in the master file", "Person other than requester", "Call note"],
            ["4", "Obtain a bank identity statement in the supplier's name", "Accounts Payable", "RIB / bank letter"],
            ["5", "Approve the change in the master file", "Finance Director", "System log"],
            ["6", "Pay a first transfer only after the change is approved", "Accounts Payable", "Payment run"]]),
        "A request that does not complete steps 1 to 5 is rejected and reported to the Finance Director."]),
    ("Annex F – Emergency purchase form", [
        T([("Field", 60 * mm, "l"), ("Content", 110 * mm, "l")], [
            ["Vessel", "Name of the vessel concerned"], ["Date and time", "When the emergency occurred"],
            ["Nature of the emergency", "Safety, pollution, seaworthiness"], ["Supplier", "Name, contact"],
            ["Estimated amount", "Net amount, currency"], ["Authorised by", "Master (name, signature)"],
            ["Regularisation PO", "Number and date (within 2 working days)"], ["Service report", "Reference, signed on board"]])]),
    ("Annex G – Supplier creation form", [
        T([("Field", 60 * mm, "l"), ("Rule", 110 * mm, "l")], [
            ["Legal name", "As per registration extract"], ["Registration number", "Extract less than 3 months old"],
            ["VAT number", "Checked on VIES; screenshot attached"], ["Address", "Registered office"],
            ["Contact e-mail and telephone", "Used for call-backs"], ["IBAN / BIC", "Bank identity statement on letterhead"],
            ["Payment terms", "Standard 30 days; other terms approved by the Finance Director"],
            ["PO required", "Yes by default; No only for framework contracts listed in section 2"],
            ["Expense account", "Proposed by Accounts Payable, validated by the Chief Accountant"]])]),
    ("Annex H – Key indicators reported monthly", [
        T([("Indicator", 90 * mm, "l"), ("Target", 40 * mm, "l"), ("Owner", 40 * mm, "l")], [
            ["Invoices booked with a PO (PO-required suppliers)", "100%", "Accounts Payable"],
            ["Invoices on hold for matching differences", "< 5%", "Accounts Payable"],
            ["Payments made after due date", "< 3%", "Accounts Payable"],
            ["Unmatched bank debits at month end", "0", "Chief Accountant"],
            ["Supplier statements reconciled", "100% of key suppliers", "Chief Accountant"],
            ["Bank detail changes without call-back", "0", "Finance Director"],
            ["POs approved above delegated limits", "0", "Finance Director"]])]),
    ("Annex I – Glossary", [
        T([("Term", 50 * mm, "l"), ("Meaning", 120 * mm, "l")], [
            ["Accrual (FNP)", "Expense recorded for goods or services received and not yet invoiced"],
            ["Cut-off", "Allocation of expenses to the period in which goods or services were received"],
            ["Deposit", "Payment made before delivery under an express contractual clause"],
            ["Duplicate", "The same invoice recorded more than once"],
            ["Lettrage", "Matching of invoices and payments on a supplier account"],
            ["Reverse charge", "VAT accounted for by the customer on intra-EU purchases"],
            ["Three-way match", "Matching of purchase order, delivery note and invoice"],
            ["Supplier statement", "List of open items sent by the supplier"],
            ["Aged payables", "Open invoices sorted by days past due date"]])]),
    ("Annex J – Version history", [
        T([("Version", 25 * mm, "l"), ("Date", 30 * mm, "l"), ("Change", 115 * mm, "l")], [
            ["v1", "12/03/2021", "First version"],
            ["v2", "20/01/2024", "Approval matrix updated; emergency purchases (section 2)"],
            ["v3", "15/01/2026", "Call-back for bank detail changes (section 6, annex E) after the 2025 internal audit"]])]),
]


# ---------------------------------------------------------------- hull & machinery policy wording
def insurance_more() -> list:
    clauses = [
        ("Clause 1 – Navigation", "The vessels are covered while at sea, in port, in dry dock or on slipways, and while "
         "laid up, within the navigation limits stated in the schedule. Towage is covered only when customary or when "
         "assistance is needed; salvage services under contract are excluded unless agreed in advance."),
        ("Clause 2 – Change of management", "The cover terminates automatically on change of the vessel's flag, "
         "classification society or manager, unless underwriters agree in writing. Azur Marine Services S.A.M. is the "
         "designated manager of the three vessels."),
        ("Clause 3 – Pollution hazard", "Loss of or damage to the vessel caused by a governmental authority acting to "
         "prevent or mitigate a pollution hazard is covered, provided it did not result from want of due diligence."),
        ("Clause 4 – Three-fourths collision liability", "Underwriters pay three-fourths of any sum the assured becomes "
         "legally liable to pay to another person by reason of the vessel coming into collision with another vessel."),
        ("Clause 5 – Sistership", "If the insured vessel collides with or receives salvage services from another vessel "
         "under the same management, the assured have the same rights as if the other vessel were owned by third parties."),
        ("Clause 6 – General average and salvage", "The policy covers the vessel's proportion of salvage, salvage charges "
         "and general average, adjusted in accordance with the York-Antwerp Rules 2016."),
        ("Clause 7 – Duty of the assured (sue and labour)", "In case of loss or misfortune, the assured and their agents "
         "must take reasonable measures to avert or minimise a loss recoverable under this insurance."),
        ("Clause 8 – Deductible", "No claim arising from an insured peril is payable unless the aggregate of all claims "
         "arising from the same accident exceeds the deductible stated in the schedule for the vessel concerned."),
        ("Clause 9 – Notice of claim and tenders", "In the event of an accident, notice must be given to the underwriters "
         "promptly and before survey, so that a surveyor may be appointed. Underwriters may take tenders for repairs."),
        ("Clause 10 – New for old", "Claims are payable without deduction new for old."),
        ("Clause 11 – Bottom treatment", "The cost of scraping, gritblasting and painting the bottom is not payable "
         "unless directly related to the repair of damage covered by this insurance."),
        ("Clause 12 – Wages and maintenance", "Wages and maintenance of the crew are not covered except in connection with "
         "general average or shifting the vessel for repairs."),
        ("Clause 13 – Agency commission", "No claim is payable for time and trouble taken by the assured to obtain and "
         "supply information or documents in respect of a claim."),
        ("Clause 14 – Unrepaired damage", "The measure of indemnity for unrepaired damage is the reasonable depreciation in "
         "the market value of the vessel, not exceeding the reasonable cost of repairs."),
        ("Clause 15 – Constructive total loss", "In ascertaining whether the vessel is a constructive total loss, the "
         "agreed value is taken as the repaired value."),
        ("Clause 16 – Disbursements", "Additional insurances on disbursements, managers' commissions, profits or freight "
         "are permitted up to 25% of the agreed value."),
        ("Clause 17 – Returns for lay-up and cancellation", "A return of premium is payable for each period of 30 "
         "consecutive days the vessel is laid up in an approved port, at the rate stated in the schedule."),
        ("Clause 18 – Premium", "The premium is payable in quarterly instalments; failure to pay an instalment within 30 "
         "days of its due date suspends the cover until payment."),
        ("Clause 19 – War exclusion", "This insurance excludes loss, damage, liability or expense caused by war, civil "
         "war, revolution, capture, seizure, mines, torpedoes or other weapons of war."),
        ("Clause 20 – Strikes and terrorism exclusion", "Loss caused by strikers, terrorists or persons acting from a "
         "political motive is excluded and insured under the separate war and strikes cover."),
        ("Clause 21 – Malicious acts exclusion", "Loss arising from detonation of an explosive or any weapon of war caused "
         "by a person acting maliciously is excluded."),
        ("Clause 22 – Radioactive contamination", "Loss caused by ionising radiation, radioactive, chemical, biological or "
         "electromagnetic weapons is excluded."),
        ("Clause 23 – Cyber exclusion", "Loss caused by the use of any computer system or software as a means of "
         "inflicting harm is excluded; navigation electronics failures from other causes remain covered."),
        ("Clause 24 – Sanctions", "Underwriters provide no cover where doing so would expose them to sanctions under UN, EU, "
         "UK or US law."),
        ("Clause 25 – Law and jurisdiction", "This insurance is governed by English law and practice; disputes are "
         "submitted to the High Court in London."),
    ]
    equip = []
    rnd = random.Random(441)
    items = ["Main engine", "Gearbox", "Generator", "Stabiliser fin", "Bow thruster", "Watermaker", "Tender (7.5 m)",
             "Jet ski", "Crane / davit", "Hydraulic passerelle", "Radar", "ECDIS workstation", "Autopilot", "Satellite dome",
             "Air conditioning plant", "Sewage treatment plant", "Fire suppression system", "Liferaft"]
    for v, n in (("M/Y Aurelia", 2), ("M/Y Selene", 2), ("S/Y Blue Horizon", 1)):
        for it in items:
            for k in range(1 if it not in ("Main engine", "Generator", "Stabiliser fin", "Liferaft") else n):
                val = D(rnd.randrange(18, 900) * 1000)
                equip.append([v, f"{it}{' ' + str(k + 1) if n > 1 and it in ('Main engine', 'Generator', 'Stabiliser fin', 'Liferaft') else ''}",
                              f"{rnd.randrange(2012, 2026)}", fmt(val)])
    return [("Policy wording", clauses[:12]), ("Policy wording (continued)", clauses[12:]),
            ("Schedule of equipment declared", [
                "Values declared by the manager for machinery-breakdown purposes (EUR, replacement value).",
                T([("Vessel", 40 * mm, "l"), ("Equipment", 70 * mm, "l"), ("Year", 20 * mm, "c"), ("Value EUR", 40 * mm, "r")], equip)])]


# ---------------------------------------------------------------- survey report
def survey_more() -> list:
    rnd = random.Random(518)
    hull = [[f"{z}", rnd.choice(["Good", "Good", "Fair", "Good"]), f"{rnd.randrange(14, 19)}.{rnd.randrange(0, 9)} mm",
             rnd.choice(["No action", "Monitor", "No action", "Touch-up coating"])]
            for z in ["Keel plate", "Bottom fwd P", "Bottom fwd S", "Bottom aft P", "Bottom aft S", "Side shell P", "Side shell S",
                      "Transom", "Bow thruster tunnel", "Sea chest 1", "Sea chest 2", "Rudder P", "Rudder S", "Skeg"]]
    safety = [["Liferaft 12p A-pack (x2)", "Service due 09/2026", "Service before 30/09/2026"],
              ["EPIRB 406 MHz", "Battery expiry 10/2026", "Replace battery and HRU"],
              ["SART (x2)", "Valid to 2028", "None"], ["Lifejackets SOLAS (x24)", "4 lights inoperative", "Replace lights"],
              ["Lifebuoys (x4)", "Good", "None"], ["Fire extinguishers (x18)", "6 due for service", "Service or replace"],
              ["Fixed CO2 system engine room", "Last test 03/2025", "Test due 03/2027"],
              ["Fire detection panel", "Good", "None"], ["Pyrotechnics", "Expire 11/2026", "Replace"],
              ["Emergency lighting", "Good", "None"], ["Medical chest category A", "Inventory partly expired", "Restock"]]
    return [
        ("Scope and method", ["The survey was carried out afloat at Quai Antoine Ier, Monaco, on 14 and 15 May 2026, then "
         "on the hard during a short lift on 16 May 2026, in the presence of the Master and the Chief Engineer. Ultrasonic "
         "thickness measurements were taken on the bottom and side shell; machinery was observed running under load.",
         "The survey is a condition survey for the manager and the owner; it is not a class or flag survey and does not "
         "replace the statutory certificates."]),
        ("Hull – thickness measurements", T([("Zone", 50 * mm, "l"), ("Condition", 30 * mm, "l"), ("Min. thickness", 35 * mm, "r"),
                                            ("Action", 55 * mm, "l")], hull)),
        ("Deck and superstructure", ["Teak deck in fair condition; caulking worn on the aft deck and the flybridge "
         "(approximately 18 m of seams). Stainless fittings in good order. Two windows on the main deck show minor "
         "delamination of the sealant.", "Anchor windlasses and chain lockers in good order; chain marked every 25 m."]),
        ("Safety equipment", T([("Item", 60 * mm, "l"), ("Status", 50 * mm, "l"), ("Recommendation", 60 * mm, "l")], safety)),
        ("Photographs", T([("No.", 15 * mm, "c"), ("Subject", 155 * mm, "l")],
                          [[str(k), s] for k, s in enumerate(["Starboard quarter blistering", "Port shaft seal", "Generator 1 exhaust elbow",
                           "Main bilge pump", "Aft deck caulking", "Liferaft certificates", "EPIRB label", "Engine room overview",
                           "Steering gear", "Shore power inlet", "Tender cradle", "Windlass"], 1)])),
        ("Recommendations and priorities", T([("No.", 12 * mm, "c"), ("Recommendation", 110 * mm, "l"), ("Priority", 25 * mm, "l"),
                                               ("Before", 23 * mm, "l")], [
            ["1", "Service both liferafts", "High", "30/09/2026"], ["2", "Replace EPIRB battery and HRU", "High", "31/10/2026"],
            ["3", "Replace main bilge pump (end of life)", "High", "Next yard"], ["4", "Renew shaft seals", "Medium", "Next haul-out"],
            ["5", "Replace generator 1 exhaust elbow", "Medium", "31/12/2026"], ["6", "Re-caulk aft deck seams", "Low", "Next yard"],
            ["7", "Replace pyrotechnics", "Medium", "30/11/2026"], ["8", "Restock medical chest", "Medium", "30/06/2026"]])),
    ]


# ---------------------------------------------------------------- lease, contracts, minutes
LEASE_MORE = [
    ("Article 1 – Désignation détaillée", ["Les locaux comprennent : un hall d'accueil de 18 m², six bureaux fermés d'une "
     "surface totale de 104 m², une salle de réunion de 28 m², un local informatique ventilé de 6 m², une kitchenette, deux "
     "sanitaires et un local d'archives de 12 m² au sous-sol.", "Un état des lieux contradictoire a été établi le 31/03/2023 "
     "et demeure annexé au présent bail."]),
    ("Article 2 – Garanties", "Le preneur fournit une garantie bancaire à première demande d'un montant égal au dépôt de "
     "garantie, émise par un établissement établi à Monaco, valable pendant toute la durée du bail et six mois au-delà."),
    ("Article 3 – Accès et sécurité", "Le preneur dispose d'un accès 24 heures sur 24 aux locaux. Les badges d'accès sont "
     "remis contre décharge ; toute perte est signalée au gestionnaire de l'immeuble dans les 24 heures."),
    ("Article 4 – Visites", "Le bailleur peut visiter les locaux une fois par an, sur rendez-vous, et pendant les six derniers "
     "mois du bail en vue de leur relocation."),
    ("Article 5 – Restitution", "En fin de bail, les locaux sont restitués en bon état de réparations locatives. Un état des "
     "lieux de sortie est établi contradictoirement ; le dépôt de garantie est restitué dans un délai de deux mois, déduction "
     "faite des sommes dues."),
    ("Article 6 – Élection de domicile", "Pour l'exécution des présentes, les parties font élection de domicile en leurs "
     "sièges respectifs. Le présent bail est soumis au droit monégasque."),
    ("Annexe – Échéancier des loyers 2026", T([("Échéance", 40 * mm, "l"), ("Période", 60 * mm, "l"), ("Loyer HT", 35 * mm, "r"),
                                                ("Provision charges", 35 * mm, "r")],
        [["01/01/2026", "Janvier – mars 2026", "24 960,00", "3 150,00"], ["01/04/2026", "Avril – juin 2026", "25 420,00", "3 150,00"],
         ["01/07/2026", "Juillet – septembre 2026", "25 420,00", "3 150,00"], ["01/10/2026", "Octobre – décembre 2026", "25 420,00", "3 150,00"]])),
]

KAIROS_MORE = [
    ("Clause 4 – Security", ["Kairos applies security measures in line with ISO/IEC 27001: multi-factor authentication for "
     "administrative access, encryption of backups, patching of servers within 14 days of a critical vendor release, and "
     "annual penetration testing of the office perimeter.", "Kairos notifies the Customer of any security incident within "
     "24 hours of detection and assists in the investigation."]),
    ("Clause 5 – Backups and restoration", "Office servers are backed up daily with 30 days of retention and monthly with "
     "12 months of retention. A restoration test is performed every quarter and documented in the monthly report."),
    ("Clause 6 – Reporting", "Kairos sends a monthly service report listing tickets, response and resolution times, "
     "backups and planned work. The report is attached to the monthly invoice."),
    ("Clause 8 – Subcontracting", "Kairos may subcontract hardware maintenance and satellite connectivity support, remaining "
     "responsible for its subcontractors."),
    ("Clause 10 – Audit", "The Customer and its statutory auditor may audit the services once a year with 15 days' notice."),
    ("Clause 11 – Reversibility", "On termination, Kairos returns all data and documentation and assists the new provider "
     "for up to 20 days at the hourly rate of schedule C."),
    ("Schedule E – Inventory under management", T([("Asset", 60 * mm, "l"), ("Location", 50 * mm, "l"), ("Qty", 15 * mm, "r"),
                                                    ("Support level", 45 * mm, "l")], [
        ["Workstations", "Office", "14", "Standard"], ["Laptops", "Office / travel", "9", "Standard"],
        ["Hosted virtual servers", "Data centre Nice", "4", "Critical"], ["Firewall cluster", "Office", "2", "Critical"],
        ["Wi-Fi access points", "Office", "6", "Standard"], ["Printers / scanners", "Office", "3", "Best effort"],
        ["Vessel network (Aurelia)", "On board", "1", "Critical"], ["Vessel network (Selene)", "On board", "1", "Critical"],
        ["Vessel network (Blue Horizon)", "On board", "1", "Critical"], ["Satellite terminals", "On board", "3", "Standard"],
        ["Microsoft 365 licences", "Cloud", "26", "Standard"], ["Accounting system (Comptaflux)", "Hosted", "1", "Critical"]])),
]

BERTH_MORE = [("Annex – Marina regulations (extract)", [
    T([("No.", 12 * mm, "c"), ("Rule", 158 * mm, "l")], [[str(k), r] for k, r in enumerate([
        "Vessels must keep their berth clean and must not discharge any waste, grey or black water in the harbour.",
        "Engines may only be run for manoeuvres and tests; generators are not permitted when shore power is available.",
        "Hot work (welding, grinding) requires a written permit from the harbour master.",
        "Refuelling is only permitted by approved suppliers, with absorbent booms deployed.",
        "Noise must be limited between 22:00 and 08:00.",
        "Tenders must not exceed 3 knots inside the harbour.",
        "Deliveries on the quay are limited to 30 minutes per vehicle and must be announced 24 hours in advance.",
        "Gangways must be lit at night and fitted with a safety net.",
        "The harbour master may move any vessel in an emergency.",
        "Divers may only work with a permit and the diving flag displayed.",
        "Vessels must display their berth number and contact details on the quay plate.",
        "Any accident or pollution must be reported immediately to the harbour master's office."], 1)])])]

ECO_MORE = [("Annexe – Tarifs 2025-2027", T([("Prestation", 90 * mm, "l"), ("Unité", 30 * mm, "l"), ("Prix HT", 30 * mm, "r")], [
    ["Collecte mensuelle (forfait)", "mois", "640,00"], ["Pompage eaux de cale", "m3", "210,00"],
    ["Nettoyage caisse à combustible", "forfait", "2 480,00"], ["Élimination déchets huileux", "tonne", "400,00"],
    ["Collecte filtres et chiffons souillés supplémentaire", "fût 200 L", "85,00"],
    ["Intervention d'urgence (hors heures ouvrées)", "intervention", "350,00"]])),
            ("Annexe – Codes déchets", T([("Code", 30 * mm, "l"), ("Désignation", 140 * mm, "l")], [
                ["13 02 05*", "Huiles minérales non chlorées de moteurs"], ["13 04 03*", "Hydrocarbures de cale provenant d'autres navigations"],
                ["15 02 02*", "Absorbants, matériaux filtrants, chiffons souillés"], ["16 01 07*", "Filtres à huile"]]))]

BOARD_MORE = [
    ("6bis. Review of the procurement policy", ["The Finance Director recalls the changes introduced in version 3 of policy "
     "PRC-FIN-04 (January 2026), in particular the call-back required for any change of supplier bank details, introduced "
     "after the 2025 internal audit.", "The Board asks for a first assessment of compliance with the new rules at its "
     "December meeting, including any purchase order approved above delegated limits."]),
    ("6ter. Yard period M/Y Aurelia", "Budget of EUR 1.42 million approved for the winter yard period in La Ciotat (hull "
     "coating, shaft seals, bilge system, interior refit of two guest cabins). Tender from three yards; decision by the CEO "
     "within the budget."),
]

AUDIT_MORE = [
    ("Calendrier détaillé", T([("Phase", 60 * mm, "l"), ("Période", 50 * mm, "l"), ("Livrable", 60 * mm, "l")], [
        ["Prise de connaissance", "Octobre 2026", "Note de planification"], ["Revue du contrôle interne", "Novembre 2026", "Lettre de recommandations"],
        ["Circularisation fournisseurs", "Janvier 2027", "Synthèse des réponses"], ["Inventaire de caisse", "31/12/2026", "PV"],
        ["Intervention finale", "Mars 2027", "Rapport sur les comptes annuels"]])),
    ("Documents à préparer par la société", ["Balance générale et grands-livres au 31/12/2026, rapprochements bancaires de "
     "décembre, balances âgées clients et fournisseurs, état des charges à payer, tableaux d'immobilisations, procès-verbaux "
     "des conseils et assemblées, contrats significatifs.", "Pour le cycle achats : échantillon de 25 factures avec bons de "
     "commande et bons de livraison, liste des modifications de coordonnées bancaires de l'exercice avec leurs justificatifs."]),
    ("Honoraires détaillés", T([("Phase", 90 * mm, "l"), ("Heures", 25 * mm, "r"), ("Montant HT", 35 * mm, "r")], [
        ["Planification et contrôle interne", "62", "8 990,00"], ["Contrôles des comptes", "118", "16 520,00"],
        ["Rapports", "21", "2 990,00"], ["Total", "201", "28 500,00"]])),
]

CHARTER_MORE = [
    ("Owner's obligations", "The owner funds the vessel's operating account monthly in advance on the basis of the approved "
     "budget, keeps the insurances in force and approves any single expense above EUR 15,000.00."),
    ("Manager's obligations", ["The manager recruits and administers the crew, organises maintenance and class surveys, "
     "manages suppliers in accordance with its procurement policy and keeps the vessel's accounts.", "The manager reports "
     "monthly: budget versus actual, cash position, crew changes and technical status."]),
    ("Accounting and audit", "Third-party costs are recharged at cost with copies of invoices. The owner may audit the "
     "vessel's accounts once a year."),
    ("Term and termination", "Indefinite term; termination by either party with three months' notice."),
]

IT_MORE = [
    ("Acceptable use", "Company devices are used for business purposes. Installation of software requires the approval of "
     "Kairos IT Services. Personal cloud storage must not be used for company documents."),
    ("E-mail security", ["External e-mails are tagged [EXTERNAL] in the subject line. Staff must check the sender's address "
     "and must never act on a request to change bank details or to pay urgently without verification by telephone on a "
     "known number.", "Suspicious e-mails are forwarded to security@azurmarine.example and deleted."]),
    ("Vessel systems", "Vessel networks are segregated from navigation systems. ECDIS and radar are never connected to the "
     "crew Wi-Fi."),
    ("Training", "Every employee follows an annual awareness session; finance staff follow an additional session on payment "
     "fraud."),
]


# ---------------------------------------------------------------- generated tables
def loan_schedule() -> list:
    """Full 60-month annuity schedule of loan PR-2025-0119 (EUR 180,000, 3.40%, from 10/02/2025)."""
    principal, r, n = Decimal("180000.00"), Decimal("0.034") / 12, 60
    pay = (principal * r / (1 - (1 + r) ** -n)).quantize(Decimal("0.01"))
    rows, bal = [], principal
    for k in range(1, n + 1):
        y, m = 2025 + (k) // 12, (k % 12) + 1
        interest = (bal * r).quantize(Decimal("0.01"))
        cap = pay - interest if k < n else bal
        bal -= cap
        rows.append([f"{k}", f"10/{m:02d}/{y}", fmt(cap, "fr"), fmt(interest, "fr"), fmt(cap + interest, "fr"), fmt(bal, "fr")])
    return [("Échéancier complet", T([("N°", 12 * mm, "c"), ("Échéance", 28 * mm, "l"), ("Capital", 30 * mm, "r"),
                                     ("Intérêts", 30 * mm, "r"), ("Échéance totale", 34 * mm, "r"), ("Capital restant dû", 36 * mm, "r")], rows))]


def pricelist_more() -> list:
    rnd = random.Random(2026)
    cats = {"Engine room": ["Fuel filter", "Oil filter", "Air filter", "Impeller kit", "V-belt", "Zinc anode", "Gasket set",
                            "Thermostat", "Injector seal kit", "Coolant hose"],
            "Lubricants": ["Lube oil 15W-40 20 L", "Lube oil 15W-40 208 L", "Gear oil 80W-90 20 L", "Hydraulic oil VG 46 20 L",
                           "Hydraulic oil VG 46 208 L", "Grease EP2 18 kg", "Stern tube oil 20 L"],
            "Deck": ["Mooring line 18 mm (per m)", "Fender F6", "Fender F8", "Boat hook", "Deck brush", "Teak cleaner 5 L",
                     "Chamois", "Snubber"],
            "Safety": ["Lifejacket 150N", "Lifejacket light", "Fire blanket", "Extinguisher 6 kg", "First aid kit",
                       "Hand flare", "Parachute rocket"],
            "Consumables": ["Nitrile gloves (100)", "Absorbent pads (200)", "Wipes (500)", "Cable ties (1000)", "Duct tape",
                            "Spray cleaner 5 L", "Bin bags (200)"]}
    out = []
    for cat, items in cats.items():
        rows = [[f"{cat[:2].upper()}-{k:03d}", it, f"{rnd.randrange(300, 90000) / 100:.2f}".replace(".", "."), rnd.choice(["pc", "box", "can", "set", "drum"])]
                for k, it in enumerate(items, 1)]
        out.append((cat, T([("Code", 25 * mm, "l"), ("Description", 90 * mm, "l"), ("Price EUR", 30 * mm, "r"), ("Unit", 25 * mm, "c")], rows)))
    return out


def mgmt_q2_more() -> list:
    v = [["M/Y Aurelia", "432", "198", "(198)", "432"], ["M/Y Selene", "283", "96", "(96)", "283"],
         ["S/Y Blue Horizon", "197", "47", "(47)", "197"], ["Total", "912", "341", "(341)", "912"]]
    return [("Contribution by vessel before overheads (EUR thousand)", T([("Vessel", 45 * mm, "l"), ("Fees", 30 * mm, "r"),
                                                    ("Recharges", 30 * mm, "r"), ("Recharged costs", 30 * mm, "r"),
                                                    ("Contribution", 30 * mm, "r")], v)),
            ("Internal control", "Implementation of the 2025 internal audit recommendations: 5 of 7 closed; the two open "
             "items (training on payment fraud, quarterly reporting of approvals above limits) are planned for Q4 2026.")]


def vat_more() -> list:
    return [("Détail des opérations imposables", T([("Ligne CA3", 25 * mm, "l"), ("Libellé", 95 * mm, "l"), ("Base HT", 30 * mm, "r"),
                                                     ("Taxe", 25 * mm, "r")], [
        ["A1", "Ventes, prestations de services", "206 510,00", "41 302,00"], ["B2", "Acquisitions intracommunautaires", "16 480,00", "3 296,00"],
        ["08", "Taux normal 20 %", "222 990,00", "44 598,00"], ["17", "TVA due sur acquisitions intracommunautaires", "", "3 296,00"],
        ["19", "Biens constituant des immobilisations", "", "0,00"], ["20", "Autres biens et services", "", "30 383,00"],
        ["23", "Total TVA déductible", "", "30 383,00"], ["28", "TVA nette due", "", "14 215,00"]])),
            ("Observations", "Déclaration souscrite par Inès Morel, Chief Accountant, le 18/09/2026. Paiement par "
             "télérèglement.")]


# ---------------------------------------------------------------- new long documents
def internal_audit_2025() -> list:
    findings = [
        ("F1", "Bank detail changes accepted on e-mail only", "High",
         "In 2 of the 6 changes of supplier bank details tested, the change was entered on the basis of an e-mail without any "
         "call-back. In one case the request came from an address that differed from the supplier's usual domain.",
         "Introduce a mandatory call-back by a person other than the requester; document it in the master file.",
         "Agreed. Policy PRC-FIN-04 will be updated in January 2026 (section 6 and annex E).", "Finance Director", "31/01/2026", "Closed"),
        ("F2", "Emergency purchases not regularised", "Medium",
         "4 emergency repairs authorised verbally on board in 2025 were never covered by a purchase order; 3 had no service "
         "report.", "Regularisation PO within 2 working days and a signed service report before payment.",
         "Agreed; emergency purchase form created (annex F).", "Operations Manager", "31/01/2026", "Closed"),
        ("F3", "POs approved above delegated limits", "Medium",
         "2 purchase orders above EUR 20,000 were approved by the Finance Director alone.",
         "Block approvals above limits in the purchasing tool; report exceptions quarterly to the Board.",
         "Agreed; quarterly reporting from Q1 2026, tool blocking planned for Q4 2026.", "Finance Director", "31/12/2026", "Open"),
        ("F4", "Duplicate invoices", "Medium",
         "1 invoice booked twice in 2025 after a supplier reminder (EUR 1,940.00); detected at the year-end supplier "
         "reconciliation.", "Search for duplicates on supplier and invoice number before booking.",
         "Agreed; duplicate check added to the monthly close.", "Chief Accountant", "31/03/2026", "Closed"),
        ("F5", "Supplier statement reconciliations", "Low",
         "Supplier statements were reconciled only at year end.", "Reconcile key supplier statements monthly.",
         "Agreed for Mediterra, Oceanic Safety and Côte d'Azur Ship Chandlers.", "Chief Accountant", "31/03/2026", "Closed"),
        ("F6", "Cut-off documentation", "Low",
         "The accrual schedule did not reference the delivery evidence.", "Attach delivery note or service report to each accrual.",
         "Agreed.", "Chief Accountant", "31/03/2026", "Closed"),
        ("F7", "Payment fraud awareness", "Medium",
         "Finance staff had not received specific training on payment fraud.", "Annual training for finance staff.",
         "Agreed; training scheduled.", "Finance Director", "31/12/2026", "Open"),
    ]
    out = [("1. Executive summary", ["This report presents the results of the internal audit of the purchase-to-pay cycle "
            "of Azur Marine Services S.A.M. for the financial year 2025, carried out in November 2025 by Riviera Internal "
            "Audit Services at the request of the Board.", "The audit identified 7 findings: 1 rated high, 4 medium and 2 "
            "low. Management has accepted all recommendations. The overall rating of the cycle is \"needs improvement\"."]),
           ("2. Scope and approach", ["Scope: purchase orders, receipt of goods and services, supplier invoices, supplier "
            "master data and payments, for the office and the three managed vessels.", "Approach: walkthroughs with the "
            "Operations Manager, Accounts Payable and the Finance Director; tests on a sample of 40 invoices, 6 changes of "
            "bank details, 25 payments and the supplier master file at 31/10/2025."]),
           ("3. Summary of findings", T([("Ref.", 14 * mm, "l"), ("Finding", 92 * mm, "l"), ("Rating", 22 * mm, "l"), ("Status", 22 * mm, "l"),
                                          ("Due", 20 * mm, "l")], [[f[0], f[1], f[2], f[7], f[6]] for f in findings]))]
    for ref, title, rating, obs, rec, resp, owner, due, status in findings:
        out.append((f"4. {ref} – {title} ({rating})", [f"Observation. {obs}", f"Recommendation. {rec}",
                                                        f"Management response. {resp} Owner: {owner}. Due: {due}."]))
    out.append(("5. Rating scale", T([("Rating", 30 * mm, "l"), ("Meaning", 140 * mm, "l")], [
        ["High", "Control weakness exposing the company to a significant loss or fraud; action within 3 months"],
        ["Medium", "Weakness that should be corrected within 12 months"], ["Low", "Improvement opportunity"]])))
    out.append(("6. Follow-up", "Riviera Internal Audit Services will review the implementation of the open actions in "
                "November 2026 and report to the Board."))
    return out


def mgmt_accounts_aug() -> list:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    rech = [98, 102, 109, 113, 114, 114, 128, 104]                              # Q2 = 341
    data = [("Management fees", [302, 302, 302, 304, 304, 304, 305, 305]),       # Q2 = 912
            ("Recharges to owners", rech),
            ("Recharged costs (at cost)", [-v for v in rech]),
            ("Personnel costs incl. social charges", [-238, -238, -239, -240, -240, -240, -241, -241]),  # Q2 = 720
            ("Office rent and charges", [-9] * 8),
            ("IT and telecom", [-6, -6, -6, -6, -7, -6, -6, -6]),
            ("Insurance (office)", [-2] * 8),
            ("Professional fees", [-3] * 8),                                      # office + IT + insurance + fees Q2 = 61
            ("Travel", [-3] * 8),
            ("Other external costs", [-16] * 8),
            ("Depreciation", [-3] * 8)]
    rows = [[name] + [str(v) if v >= 0 else f"({-v})" for v in vals] for name, vals in data]
    tot = [sum(vals[k] for _, vals in data) for k in range(8)]
    rows.append(["Operating result"] + [str(v) for v in tot])
    assert sum(data[0][1]) == 2428 and sum(rech) == 882 and -sum(data[3][1]) == 1917
    assert -sum(sum(v) for _, v in data[4:10]) == 313 and sum(tot) == 174
    cols = [("EUR thousand", 50 * mm, "l")] + [(m, 15 * mm, "r") for m in months]
    return [("Highlights", ["August 2026: management fees in line with budget; recharges to owners lower than July due to "
             "the end of the summer season.", "Cash position at 31/08/2026 comfortable; no use of the overdraft facility."]),
            ("Income statement by month (EUR thousand)", T(cols, rows)),
            ("Balance sheet summary at 31/08/2026 (EUR thousand)", T([("Item", 90 * mm, "l"), ("31/08/2026", 35 * mm, "r"),
                                                                       ("31/12/2025", 35 * mm, "r")], [
                ["Fixed assets", "151", "177"], ["Trade receivables", "318", "286"], ["Other receivables and prepayments", "44", "63"],
                ["Cash", "402", "402"], ["Total assets", "915", "928"], ["Equity (incl. provisional result)", "698", "571"],
                ["Loan PR-2025-0119", "126", "149"], ["Other liabilities incl. trade payables", "91", "208"],
                ["Total liabilities", "915", "928"]])),
            ("Budget versus actual (8 months, EUR thousand)", T([("Item", 70 * mm, "l"), ("Actual", 30 * mm, "r"), ("Budget", 30 * mm, "r"),
                                                                  ("Variance", 30 * mm, "r")], [
                ["Management fees", "2,428", "2,416", "12"], ["Recharges", "882", "850", "32"],
                ["Recharged costs", "(882)", "(850)", "(32)"], ["Personnel costs", "(1,917)", "(1,900)", "(17)"],
                ["Other costs", "(313)", "(320)", "7"], ["Depreciation", "(24)", "(24)", "0"],
                ["Operating result", "174", "172", "2"]])),
            ("Outlook", "Q4 will include the ECDIS renewal for the fleet, the preparation of the Aurelia yard period and the "
             "annual insurance renewal.")]


def telecom_detail(month: int) -> list:
    """Call-detail annex of a Riviera Telecom invoice: per-line usage (no monetary total beyond the invoice)."""
    rnd = random.Random(month * 31)
    users = ["P. Andrieu", "C. Martin", "T. Rinaldi", "I. Morel", "S. Bianchi", "Reception", "Master Aurelia", "Chief Eng. Aurelia",
             "Master Selene", "Chief Eng. Selene", "Master Blue Horizon", "Bosun Aurelia", "Operations duty phone", "Spare line"]
    rows = []
    for k, u in enumerate(users, 1):
        rows.append([f"+377 6 80 {10 + k:02d} {rnd.randrange(10, 99)} {rnd.randrange(10, 99)}", u, f"{rnd.randrange(20, 900)} min",
                     f"{rnd.randrange(1, 60)} GB", f"{rnd.randrange(0, 40)}", "Pro Unlimited"])
    return [("Usage per line", ["Detail of usage for the billing period. Amounts are included in the monthly package; "
             "no out-of-bundle charge was billed this month.",
             T([("Line", 34 * mm, "l"), ("User", 40 * mm, "l"), ("Voice", 22 * mm, "r"), ("Data", 18 * mm, "r"), ("SMS", 14 * mm, "r"),
                ("Plan", 30 * mm, "l")], rows)])]


def it_activity(month: int) -> list:
    rnd = random.Random(month * 17)
    subj = ["Password reset", "VPN access", "Printer jam", "Mailbox full", "New laptop set-up", "Vessel Wi-Fi slow",
            "Accounting system access", "Teams meeting room", "Backup check", "Firewall rule", "Phishing report", "Licence assignment"]
    rows = [[f"KIT-{month:02d}{k:03d}", f"{rnd.randrange(1, 28):02d}/{month:02d}/2026", rnd.choice(subj), rnd.choice(["P2", "P3", "P3", "P1"]),
             rnd.choice(["Office", "Aurelia", "Selene", "Blue Horizon"]), "Resolved"] for k in range(1, 27)]
    return [("Monthly service report", ["Service levels met for all priorities. Backups: 30/30 daily jobs successful; "
             "quarterly restoration test performed. No security incident.",
             T([("Ticket", 26 * mm, "l"), ("Opened", 22 * mm, "l"), ("Subject", 56 * mm, "l"), ("Prio.", 14 * mm, "c"),
                ("Site", 26 * mm, "l"), ("Status", 22 * mm, "l")], rows)])]


# ---------------------------------------------------------------- longer annexes (8-10 page documents)
def annual_accounts_2025() -> list:
    """Financial statements 2025 of Azur Marine Services S.A.M. (French GAAP presentation, EUR)."""
    bs_a = [["Immobilisations incorporelles", "18 400", "6 900", "11 500", "14 300"],
            ["Agencements et installations", "142 600", "37 120", "105 480", "119 740"],
            ["Matériel informatique", "38 400", "21 600", "16 800", "29 600"],
            ["Matériel de transport", "31 900", "12 760", "19 140", "25 520"],
            ["Dépôts et cautionnements", "24 000", "", "24 000", "24 000"],
            ["Total actif immobilisé", "255 300", "78 380", "176 920", "213 160"],
            ["Créances clients", "286 410", "", "286 410", "251 980"], ["Autres créances", "41 230", "", "41 230", "38 770"],
            ["Disponibilités", "402 180", "", "402 180", "355 620"], ["Charges constatées d'avance", "21 940", "", "21 940", "19 300"],
            ["Total actif circulant", "751 760", "", "751 760", "665 670"], ["TOTAL ACTIF", "1 007 060", "78 380", "928 680", "878 830"]]
    bs_p = [["Capital social", "450 000", "450 000"], ["Réserve légale", "45 000", "45 000"], ["Report à nouveau", "18 420", "11 260"],
            ["Résultat de l'exercice", "57 580", "47 160"], ["Total capitaux propres", "571 000", "553 420"],
            ["Emprunts auprès des établissements de crédit", "149 246", "0"], ["Dettes fournisseurs", "84 310", "92 470"],
            ["Dettes fiscales et sociales", "121 920", "118 300"], ["Autres dettes", "2 204", "114 640"],
            ["Total dettes", "357 680", "325 410"], ["TOTAL PASSIF", "928 680", "878 830"]]
    pl = [["Chiffre d'affaires – honoraires de gestion", "3 516 000", "3 402 000"], ["Refacturations aux armateurs", "1 271 400", "1 188 300"],
          ["Total produits d'exploitation", "4 787 400", "4 590 300"], ["Achats refacturés et sous-traitance", "(1 263 900)", "(1 181 700)"],
          ["Autres achats et charges externes", "(512 300)", "(496 600)"], ["Impôts et taxes", "(21 400)", "(20 900)"],
          ["Salaires et traitements", "(2 108 600)", "(2 041 200)"], ["Charges sociales", "(756 300)", "(733 900)"],
          ["Dotations aux amortissements", "(38 900)", "(36 200)"], ["Résultat d'exploitation", "86 000", "79 800"],
          ["Résultat financier", "(5 120)", "1 240"], ["Résultat exceptionnel", "0", "(12 300)"],
          ["Impôt sur les bénéfices", "(23 300)", "(21 580)"], ["Résultat net", "57 580", "47 160"]]
    notes = [
        ("Note 1 – Règles et méthodes comptables", ["Les comptes annuels sont établis conformément au plan comptable "
         "applicable en Principauté de Monaco, selon les principes de prudence, de permanence des méthodes et "
         "d'indépendance des exercices.", "Les immobilisations sont amorties selon le mode linéaire : agencements 10 ans, "
         "matériel informatique 3 ans, matériel de transport 5 ans."]),
        ("Note 2 – Chiffre d'affaires", "Les honoraires de gestion sont facturés mensuellement aux armateurs selon les "
         "contrats de gestion. Les refacturations correspondent aux dépenses engagées pour le compte des navires et "
         "refacturées à l'euro près, sans marge."),
        ("Note 3 – Charges à payer", T([("Nature", 100 * mm, "l"), ("31/12/2025", 35 * mm, "r"), ("31/12/2024", 35 * mm, "r")], [
            ["Fournisseurs – factures non parvenues", "18 640", "22 310"], ["Congés payés", "64 200", "61 900"],
            ["Charges sociales sur congés", "23 100", "22 300"], ["Honoraires d'audit", "9 500", "9 200"], ["Total", "115 440", "115 710"]])),
        ("Note 4 – Emprunt", "Emprunt de 180 000 € contracté en janvier 2025 pour l'aménagement des bureaux, au taux fixe de "
         "3,40 %, remboursable en 60 mensualités constantes ; les échéances sont prélevées sur le compte de la société mère, "
         "qui les refacture. Capital restant dû au 31/12/2025 : 149 245,73 €."),
        ("Note 5 – Engagements hors bilan", ["Bail des bureaux : loyers restant à courir jusqu'au 31/03/2032 : 616 000 € "
         "environ.", "Garantie bancaire au profit du bailleur : 24 000 €."]),
        ("Note 6 – Effectif", T([("Catégorie", 100 * mm, "l"), ("2025", 35 * mm, "r"), ("2024", 35 * mm, "r")], [
            ["Direction", "3", "3"], ["Finance et administration", "5", "5"], ["Opérations et technique", "6", "5"],
            ["Équipages sous contrat de gestion", "28", "27"], ["Total", "42", "40"]])),
        ("Note 7 – Événements postérieurs à la clôture", "Néant. La procédure achats PRC-FIN-04 a été mise à jour le "
         "15/01/2026 (version 3) à la suite de l'audit interne du cycle achats."),
        ("Note 8 – Parties liées", "Azur Marine Charter SARL (Antibes) et Azur Yachting Group S.A.M. (société mère) sont des "
         "parties liées ; les transactions avec elles sont conclues à des conditions normales de marché."),
    ]
    return [("Bilan actif au 31/12/2025 (EUR)", T([("Poste", 62 * mm, "l"), ("Brut", 27 * mm, "r"), ("Amort.", 27 * mm, "r"),
                                                    ("Net 2025", 27 * mm, "r"), ("Net 2024", 27 * mm, "r")], bs_a)),
            ("Bilan passif au 31/12/2025 (EUR)", T([("Poste", 100 * mm, "l"), ("2025", 35 * mm, "r"), ("2024", 35 * mm, "r")], bs_p)),
            ("Compte de résultat 2025 (EUR)", T([("Poste", 100 * mm, "l"), ("2025", 35 * mm, "r"), ("2024", 35 * mm, "r")], pl)),
            ("Tableau des immobilisations (EUR)", T([("Poste", 60 * mm, "l"), ("01/01/2025", 28 * mm, "r"), ("Acquisitions", 28 * mm, "r"),
                                                      ("Cessions", 24 * mm, "r"), ("31/12/2025", 30 * mm, "r")], [
                ["Immobilisations incorporelles", "12 600", "5 800", "0", "18 400"], ["Agencements", "142 600", "0", "0", "142 600"],
                ["Matériel informatique", "31 200", "7 200", "0", "38 400"], ["Matériel de transport", "31 900", "0", "0", "31 900"],
                ["Total", "218 300", "13 000", "0", "231 300"]]))] + notes + [
            ("Rapport de gestion – extrait", ["L'exercice 2025 a été marqué par la reconduction des trois mandats de gestion "
             "et une progression de 3,4 % des honoraires. Les refacturations aux armateurs progressent avec l'activité "
             "technique des navires.", "Le conseil propose d'affecter le résultat de 57 580 € au report à nouveau."]),
            ("Approbation", "Comptes arrêtés par le conseil d'administration du 24/03/2026 et approuvés par l'assemblée "
             "générale ordinaire du 25/06/2026.")]


def audit_samples() -> list:
    rnd = random.Random(2025)
    sup = ["Mediterra Marine Supplies", "Côte d'Azur Ship Chandlers", "Marina Fuel Services", "Harbor Parts", "SeaGlass Coatings",
           "Provence Hydraulique", "Sud Marine Électricité", "Oceanic Safety Europe", "Northstar Yacht Services", "Liguria Marine Electronics",
           "Monaco Rigging & Sails", "CrewLink Maritime", "Le Marché du Port", "EcoMarine Waste Services", "Kairos IT Services"]
    inv_rows, pay_rows = [], []
    for k in range(1, 41):
        s = rnd.choice(sup)
        res = rnd.choice(["OK"] * 8 + ["No PO", "No service report", "OK"])
        inv_rows.append([f"S{k:02d}", s, f"{rnd.randrange(1, 29):02d}/{rnd.randrange(1, 11):02d}/2025",
                         f"{rnd.randrange(400, 26000):,}.00", res])
    for k in range(1, 26):
        s = rnd.choice(sup)
        pay_rows.append([f"P{k:02d}", s, f"{rnd.randrange(1, 29):02d}/{rnd.randrange(1, 11):02d}/2025",
                         f"{rnd.randrange(400, 26000):,}.00", rnd.choice(["IBAN on file"] * 9 + ["IBAN changed (F1)"])])
    return [("Annex 1 – Invoices tested", T([("Ref.", 14 * mm, "l"), ("Supplier", 66 * mm, "l"), ("Date", 26 * mm, "l"),
                                            ("Amount EUR", 30 * mm, "r"), ("Result", 34 * mm, "l")], inv_rows)),
            ("Annex 2 – Payments tested", T([("Ref.", 14 * mm, "l"), ("Supplier", 66 * mm, "l"), ("Date", 26 * mm, "l"),
                                            ("Amount EUR", 30 * mm, "r"), ("Bank details", 34 * mm, "l")], pay_rows)),
            ("Annex 3 – Persons met", T([("Name", 50 * mm, "l"), ("Function", 70 * mm, "l"), ("Date", 50 * mm, "l")], [
                ["Philippe Andrieu", "Chief Executive Officer", "03/11/2025"], ["Claire Martin", "Finance Director", "03/11/2025"],
                ["Thomas Rinaldi", "Operations Manager", "04/11/2025"], ["Inès Morel", "Chief Accountant", "05/11/2025"],
                ["Sofia Bianchi", "Accounts Payable Accountant", "05/11/2025"], ["Capt. James Whitfield", "Master, M/Y Aurelia", "06/11/2025"]]))]


def insurance_claims() -> list:
    return [("Claims history 2021-2025 (EUR)", T([("Year", 18 * mm, "c"), ("Vessel", 40 * mm, "l"), ("Event", 70 * mm, "l"),
                                                   ("Paid", 22 * mm, "r"), ("Status", 20 * mm, "l")], [
        ["2021", "M/Y Selene", "Grounding, propeller and shaft damage", "142,800", "Closed"],
        ["2022", "M/Y Aurelia", "Contact with quay during mooring", "38,450", "Closed"],
        ["2023", "S/Y Blue Horizon", "Dismasting in squall", "211,300", "Closed"],
        ["2024", "M/Y Aurelia", "Generator crankshaft failure", "96,200", "Closed"],
        ["2025", "M/Y Selene", "Lightning strike, electronics", "27,900", "Closed"]])),
            ("Premium calculation 2026", T([("Vessel", 50 * mm, "l"), ("Agreed value", 40 * mm, "r"), ("Rate", 25 * mm, "r"),
                                            ("Annual premium", 40 * mm, "r")], [
                ["M/Y Aurelia", "38,500,000.00", "0.118%", "45,430.00"], ["M/Y Selene", "17,200,000.00", "0.120%", "20,640.00"],
                ["S/Y Blue Horizon", "6,900,000.00", "0.129%", "8,930.00"], ["Total", "62,600,000.00", "", "75,000.00"]])),
            ("Instalments", T([("Instalment", 40 * mm, "l"), ("Due date", 40 * mm, "l"), ("Amount EUR", 40 * mm, "r")], [
                ["Q1 2026", "15/01/2026", "18,750.00"], ["Q2 2026", "15/04/2026", "18,750.00"],
                ["Q3 2026", "16/07/2026", "18,750.00"], ["Q4 2026", "15/10/2026", "18,750.00"]]))]


def survey_zones() -> list:
    rnd = random.Random(77)
    out = []
    for zone, items in [("Main deck", ["Teak deck", "Hatches", "Windows", "Doors", "Handrails", "Lighting", "Drainage"]),
                        ("Upper deck and flybridge", ["Hardtop", "Helm station", "Radar arch", "Sunbeds", "Bar unit", "Crane"]),
                        ("Guest accommodation", ["Master cabin", "VIP cabin", "Twin cabin 1", "Twin cabin 2", "Bathrooms", "HVAC"]),
                        ("Crew area and galley", ["Crew mess", "Crew cabins", "Galley equipment", "Laundry", "Cold rooms"]),
                        ("Engine room", ["Main engine P", "Main engine S", "Gearboxes", "Generator 1", "Generator 2", "Fuel separators",
                                         "Bilge system", "Fire pumps", "Ventilation", "Watermakers"]),
                        ("Steering and propulsion", ["Steering gear", "Rudder stocks", "Shaft lines", "Propellers", "Stabilisers",
                                                     "Bow thruster"])]:
        rows = [[it, rnd.choice(["Good", "Good", "Fair", "Good", "Satisfactory"]),
                 rnd.choice(["No defect noted", "Minor wear", "Cosmetic marks", "Serviced 2025", "Monitor", "No defect noted"])]
                for it in items]
        out.append((f"Inspection – {zone}", ["Visual inspection and function test in the presence of the Chief Engineer.",
                    T([("Item", 60 * mm, "l"), ("Condition", 35 * mm, "l"), ("Remarks", 75 * mm, "l")], rows)]))
    return out


def lease_inventory() -> list:
    rooms = ["Hall d'accueil", "Bureau 1 (direction)", "Bureau 2", "Bureau 3", "Bureau 4", "Bureau 5", "Bureau 6",
             "Salle de réunion", "Local informatique", "Kitchenette", "Sanitaires", "Archives (sous-sol)"]
    elems = ["Sols", "Murs", "Plafonds", "Menuiseries", "Électricité", "Climatisation"]
    rnd = random.Random(323)
    rows = [[r, e, rnd.choice(["Bon état", "Bon état", "État d'usage", "Neuf"]), rnd.choice(["", "", "Rayures légères", "Traces"])]
            for r in rooms for e in elems]
    return [("Annexe – État des lieux d'entrée du 31/03/2023", T([("Pièce", 50 * mm, "l"), ("Élément", 35 * mm, "l"),
                                                                   ("État", 35 * mm, "l"), ("Observations", 50 * mm, "l")], rows))]


def premium_schedule(number: str) -> list:
    return [("Premium schedule", ["Breakdown of the premium invoiced, as per the policy schedule.",
             T([("Cover", 70 * mm, "l"), ("Vessel", 40 * mm, "l"), ("Basis", 35 * mm, "l"), ("Amount EUR", 25 * mm, "r")],
               [["Hull & machinery" if "2981" in number else "P&I – crew extension", "Fleet" if "2981" in number else "M/Y Selene",
                 "Quarterly instalment" if "2981" in number else "Additional crew (4)",
                 "18,750.00" if "2981" in number else "2,140.00"]]),
             "Insurance premiums are exempt from VAT. Insurance premium tax, where applicable, is borne by the insurer.",
             "Payment within 15 days to the broker's client account; cover is suspended if an instalment remains unpaid 30 "
             "days after its due date (clause 18)."])]
