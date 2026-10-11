"""The fictional accounting world behind AccountingBench (single source of truth).

Every document of the corpus is rendered from these objects and every expected answer is computed from them, so a
figure can never disagree between a document and the ground truth. All companies, people, addresses, VAT numbers and
IBANs are fictional (IBANs carry valid check digits; e-mail domains use the reserved .example TLD).

Scenario: Azur Marine Services S.A.M. (yacht management, Monaco) closes September 2026. July and August give history
(aged balance, payments of earlier invoices); June items appear only as opening balances.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from common import D, date, iban, prev_business_day, q2

# ---------------------------------------------------------------- entities and people

ENTITIES = {
    "AMS": dict(name="Azur Marine Services S.A.M.", street="7 Quai Antoine Ier", city="98000 Monaco",
                country="Principality of Monaco", vat="FR 64 000 512 748", reg="RCI 09 S 05127",
                nis="NIS 7022Z 08412", capital="Share capital EUR 450,000", phone="+377 97 70 41 00",
                email="accounts.payable@azurmarine.example", web="www.azurmarine.example"),
    "AMC": dict(name="Azur Marine Charter SARL", street="12 Avenue de Verdun", city="06600 Antibes",
                country="France", vat="FR 31 812 345 678", reg="RCS Antibes 812 345 678",
                nis="SIRET 812 345 678 00021", capital="Capital social 60 000 EUR", phone="+33 4 93 34 18 20",
                email="compta@azurcharter.example", web="www.azurcharter.example"),
}

PEOPLE = {
    "ceo": ("Philippe Andrieu", "Chief Executive Officer"),
    "fd": ("Claire Martin", "Finance Director"),
    "ops": ("Thomas Rinaldi", "Operations Manager"),
    "chief": ("Inès Morel", "Chief Accountant"),
    "ap": ("Sofia Bianchi", "Accounts Payable Accountant"),
    "captain": ("Capt. James Whitfield", "Master, M/Y Aurelia"),
    "engineer": ("Marco Ferri", "Chief Engineer, M/Y Selene"),
}
EMAILS = {
    "ceo": "p.andrieu@azurmarine.example", "fd": "c.martin@azurmarine.example", "ops": "t.rinaldi@azurmarine.example",
    "chief": "i.morel@azurmarine.example", "ap": "s.bianchi@azurmarine.example",
    "captain": "master.aurelia@azurmarine.example", "engineer": "chiefeng.selene@azurmarine.example",
    "accounting": "accounting@azurmarine.example", "operations": "operations@azurmarine.example",
}
# Procurement policy approval matrix (net amount of the PO, EUR)
APPROVAL_MATRIX = [(D("5000.00"), "ops"), (D("20000.00"), "fd"), (None, "ceo")]
RANK = {"ops": 1, "fd": 2, "ceo": 3}

VESSELS = {"AURELIA": "M/Y Aurelia (52 m)", "SELENE": "M/Y Selene (38 m)", "BLUE": "S/Y Blue Horizon (31 m)"}

BANK = dict(name="Banque Riviera Monaco", short="BRM", street="21 Boulevard des Moulins", city="98000 Monaco",
            bic="BRMCMCMXXXX", account_iban=iban("MC", "12739 00001 00021548763 18"),
            account_no="00021548763", branch="Agence Monte-Carlo Moulins")


def required_approver(net: Decimal) -> str:
    for limit, who in APPROVAL_MATRIX:
        if limit is None or net <= limit:
            return who
    raise AssertionError


# ---------------------------------------------------------------- suppliers

@dataclass
class Supplier:
    code: str
    name: str
    short: str  # name as truncated on bank statements
    street: str
    city: str
    country: str
    vat_id: str
    reg: str
    iban: str
    bic: str
    bank: str
    email: str
    phone: str
    terms: int  # payment terms in days from invoice date
    lang: str  # en | fr
    style: str  # invoice layout: modern | classic | din | fr
    num: str  # number format en | fr | de
    dstyle: str  # date format slash | dot | dash
    po_required: bool
    account: str
    expense: str
    regime: str  # VAT20 | RC (EU reverse charge / intra-EU) | EXEMPT | MIXED
    color: str
    activity: str
    created: dt.date
    logo: str = "circle"


def _s(**kw) -> Supplier:
    return Supplier(**kw)


SUPPLIERS: dict[str, Supplier] = {s.code: s for s in [
    _s(code="MED", name="Mediterra Marine Supplies S.A.M.", short="MEDITERRA MARINE SUPPL", street="4 Rue du Gabian",
       city="98000 Monaco", country="Monaco", vat_id="FR 23 000 487 115", reg="RCI 02 S 03981",
       iban=iban("MC", "11469 00010 00034567890 52"), bic="MEDBMCM1XXX", bank="Crédit Monégasque du Port",
       email="billing@mediterra-marine.example", phone="+377 92 05 61 40", terms=30, lang="en", style="modern",
       num="en", dstyle="slash", po_required=True, account="401MED", expense="602200", regime="VAT20",
       color="#0B5D7A", activity="Ship chandlery & engine-room consumables", created=date(14, 3, 2019), logo="wave"),
    _s(code="SEA", name="SeaGlass Coatings S.r.l.", short="SEAGLASS COATINGS SRL", street="Via del Molo 18",
       city="16128 Genova (GE)", country="Italy", vat_id="IT 02874130995", reg="REA GE-458812",
       iban=iban("IT", "X 03069 01400 000012345678"), bic="SGCOITGGXXX", bank="Banca Ligure di Levante",
       email="amministrazione@seaglass-coatings.example", phone="+39 010 247 3381", terms=30, lang="en",
       style="classic", num="en", dstyle="slash", po_required=True, account="401SEA", expense="602300", regime="RC",
       color="#2E7D32", activity="Marine coatings & antifouling", created=date(2, 2, 2021), logo="drop"),
    _s(code="HAR", name="Harbor Parts B.V.", short="HARBOR PARTS BV", street="Waalhaven Oostzijde 112",
       city="3087 BM Rotterdam", country="Netherlands", vat_id="NL 8571.23.904.B01", reg="KvK 57123904",
       iban=iban("NL", "HBPB 0417 2299 81"), bic="HBPBNL2AXXX", bank="Havenbank Rotterdam",
       email="invoices@harborparts.example", phone="+31 10 428 7710", terms=14, lang="en", style="din", num="en",
       dstyle="dash", po_required=True, account="401HAR", expense="602200", regime="RC", color="#C62828",
       activity="Propulsion & shaft-line spare parts", created=date(9, 5, 2022), logo="square"),
    _s(code="MFS", name="Marina Fuel Services S.A.M.", short="MARINA FUEL SERVICES", street="Darse Sud, Port Hercule",
       city="98000 Monaco", country="Monaco", vat_id="FR 58 000 390 266", reg="RCI 98 S 03390",
       iban=iban("MC", "11469 00020 00051122334 07"), bic="MEDBMCM1XXX", bank="Crédit Monégasque du Port",
       email="accounts@marinafuel.example", phone="+377 93 30 22 18", terms=30, lang="en", style="modern",
       num="en", dstyle="slash", po_required=True, account="401MFS", expense="606100", regime="VAT20",
       color="#EF6C00", activity="Marine fuel bunkering", created=date(20, 1, 2018), logo="flame"),
    _s(code="OSE", name="Oceanic Safety Europe GmbH", short="OCEANIC SAFETY EUROPE", street="Am Sandtorkai 41",
       city="20457 Hamburg", country="Germany", vat_id="DE 318 772 405", reg="Amtsgericht Hamburg HRB 148 223",
       iban=iban("DE", "20050550 1288 3311 47"), bic="HASPDEHHXXX", bank="Hanseatische Sparbank",
       email="rechnung@oceanic-safety.example", phone="+49 40 3009 4410", terms=30, lang="en", style="din",
       num="de", dstyle="dot", po_required=True, account="401OSE", expense="606800", regime="RC", color="#1565C0",
       activity="Life-saving & fire-fighting equipment", created=date(7, 4, 2020), logo="ring"),
    _s(code="NYS", name="Northstar Yacht Services SARL", short="NORTHSTAR YACHT SERV", street="Port Vauban, Quai Henri Rambaud",
       city="06600 Antibes", country="France", vat_id="FR 72 529 884 103", reg="RCS Antibes 529 884 103",
       iban=iban("FR", "30004 01234 00010987654 82"), bic="BNPAFRPPANT", bank="Banque Nationale du Littoral",
       email="facturation@northstar-yachts.example", phone="+33 4 93 61 77 02", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=True, account="401NYS", expense="615500", regime="VAT20",
       color="#37474F", activity="Yacht technical services", created=date(11, 6, 2019), logo="star"),
    _s(code="CAS", name="Côte d'Azur Ship Chandlers SAS", short="COTE D AZUR SHIP CHAND", street="Quai Cassini 9",
       city="06300 Nice", country="France", vat_id="FR 05 441 902 377", reg="RCS Nice 441 902 377",
       iban=iban("FR", "10096 18045 00078123456 39"), bic="CMCIFRPPXXX", bank="Crédit Maritime Azur",
       email="compta@ca-shipchandlers.example", phone="+33 4 93 55 21 90", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=True, account="401CAS", expense="602200", regime="VAT20",
       color="#00838F", activity="Avitaillement & accastillage", created=date(3, 9, 2017), logo="anchor"),
    _s(code="LME", name="Liguria Marine Electronics S.r.l.", short="LIGURIA MARINE ELECTR", street="Corso Trento e Trieste 77",
       city="18038 Sanremo (IM)", country="Italy", vat_id="IT 01593270087", reg="REA IM-139021",
       iban=iban("IT", "K 06175 22700 000004417302"), bic="CRGEITGG183", bank="Cassa di Risparmio del Ponente",
       email="amministrazione@lme-sanremo.example", phone="+39 0184 50 31 22", terms=30, lang="en", style="classic",
       num="en", dstyle="slash", po_required=True, account="401LME", expense="615600", regime="RC", color="#6A1B9A",
       activity="Navigation electronics", created=date(18, 10, 2020), logo="radar"),
    _s(code="PRH", name="Provence Hydraulique SARL", short="PROVENCE HYDRAULIQUE", street="ZI Toulon Est, 145 Rue de l'Ancienne Mine",
       city="83130 La Garde", country="France", vat_id="FR 46 389 117 254", reg="RCS Toulon 389 117 254",
       iban=iban("FR", "16807 00025 31298745632 17"), bic="CCBPFRPPTLN", bank="Banque Populaire du Var",
       email="factures@provence-hydraulique.example", phone="+33 4 94 08 31 70", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=True, account="401PRH", expense="602200", regime="VAT20",
       color="#AD1457", activity="Hydraulique industrielle et marine", created=date(25, 1, 2022), logo="hex"),
    _s(code="RVE", name="Riviera Electronics SAS", short="RIVIERA ELECTRONICS", street="88 Boulevard de la Croisette",
       city="06400 Cannes", country="France", vat_id="FR 90 801 223 559", reg="RCS Cannes 801 223 559",
       iban=iban("FR", "30066 10947 00020145872 44"), bic="CMCIFRPPXXX", bank="Crédit Maritime Azur",
       email="adv@riviera-electronics.example", phone="+33 4 92 98 40 15", terms=30, lang="fr", style="modern",
       num="fr", dstyle="slash", po_required=True, account="401RVE", expense="218300", regime="VAT20",
       color="#283593", activity="Sûreté et électronique embarquée", created=date(30, 6, 2023), logo="shield"),
    _s(code="MRS", name="Monaco Rigging & Sails S.A.R.L.", short="MONACO RIGGING SAILS", street="2 Rue de la Lüjerneta",
       city="98000 Monaco", country="Monaco", vat_id="FR 19 000 533 702", reg="RCI 11 S 05337",
       iban=iban("MC", "12739 00001 00030022451 76"), bic="BRMCMCMXXXX", bank="Banque Riviera Monaco",
       email="office@monacorigging.example", phone="+377 93 50 88 12", terms=30, lang="en", style="classic",
       num="en", dstyle="slash", po_required=True, account="401MRS", expense="615500", regime="VAT20",
       color="#4E342E", activity="Rigging, sails & deck hardware", created=date(5, 5, 2018), logo="sail"),
    _s(code="VPN", name="Var Pneumatique SAS", short="VAR PNEUMATIQUE", street="Parc d'activités de Brégaillon, Lot 14",
       city="83500 La Seyne-sur-Mer", country="France", vat_id="FR 62 494 556 018", reg="RCS Toulon 494 556 018",
       iban=iban("FR", "17607 00001 70212345678 96"), bic="CCBPFRPPMAR", bank="Banque Populaire du Var",
       email="contact@var-pneumatique.example", phone="+33 4 94 30 12 65", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=True, account="401VPN", expense="215400", regime="VAT20",
       color="#558B2F", activity="Compresseurs et air comprimé", created=date(12, 9, 2026), logo="circle"),
    _s(code="SME", name="Sud Marine Électricité SARL", short="SUD MARINE ELECTRICITE", street="31 Quai Bonaparte",
       city="06500 Menton", country="France", vat_id="FR 84 512 663 970", reg="RCS Nice 512 663 970",
       iban=iban("FR", "30003 01870 00050244781 12"), bic="SOGEFRPPXXX", bank="Société Bancaire du Sud",
       email="compta@sudmarine-elec.example", phone="+33 4 93 35 74 41", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=True, account="401SME", expense="615500", regime="VAT20",
       color="#F9A825", activity="Électricité marine", created=date(8, 2, 2020), logo="bolt"),
    _s(code="QMR", name="Quick Marine Repairs", short="QUICK MARINE REPAIRS", street="", city="Monaco",
       country="Monaco", vat_id="", reg="", iban=iban("MC", "11469 00030 00072210091 60"), bic="MEDBMCM1XXX",
       bank="Crédit Monégasque du Port", email="qmr.monaco@mail.example", phone="+377 6 40 51 22 87", terms=0,
       lang="en", style="plain", num="en", dstyle="slash", po_required=True, account="401QMR", expense="615500",
       regime="VAT20", color="#000000", activity="Diving & underwater repairs", created=date(16, 3, 2026)),
    _s(code="MBM", name="Monaco Berth Management S.A.M.", short="MONACO BERTH MGMT", street="Quai Antoine Ier, Capitainerie Nord",
       city="98000 Monaco", country="Monaco", vat_id="FR 40 000 211 860", reg="RCI 95 S 02118",
       iban=iban("MC", "12739 00001 00012233445 30"), bic="BRMCMCMXXXX", bank="Banque Riviera Monaco",
       email="billing@monacoberth.example", phone="+377 97 77 30 00", terms=10, lang="en", style="classic",
       num="en", dstyle="slash", po_required=False, account="401MBM", expense="613200", regime="VAT20",
       color="#1A237E", activity="Berth rental & marina services", created=date(1, 1, 2016), logo="anchor"),
    _s(code="RTL", name="Riviera Telecom S.A.M.", short="RIVIERA TELECOM", street="25 Boulevard de Suisse",
       city="98000 Monaco", country="Monaco", vat_id="FR 11 000 102 554", reg="RCI 97 S 03255",
       iban=iban("MC", "11469 00010 00099001122 44"), bic="MEDBMCM1XXX", bank="Crédit Monégasque du Port",
       email="factures@rivieratelecom.example", phone="+377 99 66 33 00", terms=14, lang="en", style="modern",
       num="en", dstyle="slash", po_required=False, account="401RTL", expense="626000", regime="VAT20",
       color="#D81B60", activity="Telecommunications", created=date(1, 1, 2016), logo="signal"),
    _s(code="CRW", name="CrewLink Maritime Ltd", short="CREWLINK MARITIME LTD", street="Level 3, Portomaso Business Tower",
       city="STJ 4011 St Julian's", country="Malta", vat_id="MT 2391 5508", reg="Registration C 61744",
       iban=iban("MT", "VALL 22013 000000040018776", ), bic="VALLMTMTXXX", bank="Valletta Merchant Bank",
       email="finance@crewlink.example", phone="+356 2138 4400", terms=30, lang="en", style="din", num="en",
       dstyle="slash", po_required=False, account="401CRW", expense="621100", regime="RC", color="#00695C",
       activity="Crew recruitment & management", created=date(4, 4, 2017), logo="ring"),
    _s(code="LMP", name="Le Marché du Port SARL", short="LE MARCHE DU PORT", street="Place d'Armes 3",
       city="98000 Monaco", country="Monaco", vat_id="FR 77 000 455 019", reg="RCI 04 S 04550",
       iban=iban("MC", "12739 00001 00045501900 11"), bic="BRMCMCMXXXX", bank="Banque Riviera Monaco",
       email="pro@marcheduport.example", phone="+377 93 30 75 75", terms=15, lang="fr", style="fr", num="fr",
       dstyle="slash", po_required=False, account="401LMP", expense="607100", regime="MIXED", color="#E65100",
       activity="Avitaillement alimentaire", created=date(10, 2, 2018), logo="leaf"),
    _s(code="ECO", name="EcoMarine Waste Services SAS", short="ECOMARINE WASTE SERV", street="Port Lympia, Quai du Commerce",
       city="06300 Nice", country="France", vat_id="FR 29 750 118 862", reg="RCS Nice 750 118 862",
       iban=iban("FR", "10278 08900 00020311458 63"), bic="CMCIFR2AXXX", bank="Crédit Mutuel Côte d'Azur",
       email="facturation@ecomarine-waste.example", phone="+33 4 93 89 40 60", terms=30, lang="fr", style="fr",
       num="fr", dstyle="slash", po_required=False, account="401ECO", expense="611500", regime="VAT20",
       color="#2E7D32", activity="Collecte et traitement des déchets marins", created=date(12, 12, 2018), logo="leaf"),
    _s(code="NTS", name="NavTech Systems GmbH", short="NAVTECH SYSTEMS GMBH", street="Am Wall 162",
       city="28195 Bremen", country="Germany", vat_id="DE 296 118 734", reg="Amtsgericht Bremen HRB 31877",
       iban=iban("DE", "29050101 0082 6611 93"), bic="SBREDE22XXX", bank="Weser Sparkasse",
       email="billing@navtech-systems.example", phone="+49 421 6990 210", terms=30, lang="en", style="din",
       num="de", dstyle="dot", po_required=True, account="401NTS", expense="651100", regime="RC", color="#0277BD",
       activity="ECDIS & navigation software", created=date(6, 9, 2019), logo="radar"),
    _s(code="LIB", name="Lighthouse Insurance Brokers S.A.M.", short="LIGHTHOUSE INSURANCE", street="9 Avenue des Citronniers",
       city="98000 Monaco", country="Monaco", vat_id="FR 35 000 318 640", reg="RCI 99 S 03186",
       iban=iban("MC", "11469 00010 00031864000 27"), bic="MEDBMCM1XXX", bank="Crédit Monégasque du Port",
       email="premiums@lighthouse-brokers.example", phone="+377 97 98 51 51", terms=15, lang="en", style="classic",
       num="en", dstyle="slash", po_required=False, account="401LIB", expense="616000", regime="EXEMPT",
       color="#455A64", activity="Marine insurance broking", created=date(1, 1, 2016), logo="tower"),
    _s(code="ACS", name="Azure Clean Services SARL", short="AZURE CLEAN SERVICES", street="17 Rue Grimaldi",
       city="98000 Monaco", country="Monaco", vat_id="FR 52 000 604 881", reg="RCI 13 S 06048",
       iban=iban("MC", "12739 00001 00060488100 95"), bic="BRMCMCMXXXX", bank="Banque Riviera Monaco",
       email="admin@azureclean.example", phone="+377 93 25 60 60", terms=30, lang="fr", style="fr", num="fr",
       dstyle="slash", po_required=False, account="401ACS", expense="615200", regime="VAT20", color="#039BE5",
       activity="Nettoyage de locaux professionnels", created=date(1, 9, 2021), logo="drop"),
    _s(code="KIT", name="Kairos IT Services SAS", short="KAIROS IT SERVICES", street="Les Templiers, 2400 Route des Colles",
       city="06410 Biot – Sophia Antipolis", country="France", vat_id="FR 13 823 447 109", reg="RCS Grasse 823 447 109",
       iban=iban("FR", "30004 00819 00011122233 55"), bic="BNPAFRPPNIC", bank="Banque Nationale du Littoral",
       email="billing@kairos-it.example", phone="+33 4 89 12 30 30", terms=30, lang="en", style="modern",
       num="en", dstyle="slash", po_required=False, account="401KIT", expense="615600", regime="VAT20",
       color="#5E35B1", activity="Managed IT services", created=date(15, 1, 2022), logo="hex"),
]}

# Payees that are NOT in the supplier master file
OUTSIDE_PAYEES = {
    "DUBOIS": dict(name="DUBOIS JULIEN", iban=iban("FR", "20041 01005 05012345K02 33"), bic="PSSTFRPPMAR"),
    "BLUEWATER": dict(name="BLUEWATER CONSULTING SARL", iban=iban("FR", "30027 17521 00021884410 61"),
                      bic="CMCIFRPPXXX"),
}
# Bank details announced in the e-mail of 14/09/2026 (sender domain lme-sanremo-it.example, not the master-file domain)
LME_NEW_IBAN = iban("LT", "32500 00012345678")
LME_NEW_BIC = "UAPELT22XXX"


# ---------------------------------------------------------------- documents of the purchase cycle

@dataclass
class Line:
    desc: str
    qty: Decimal
    unit: str
    price: Decimal
    rate: Decimal  # VAT rate as a fraction (0.20, 0.055, 0)
    sku: str = ""

    @property
    def amount(self) -> Decimal:
        return q2(self.qty * self.price)


def L(desc, qty, unit, price, rate="0.20", sku="") -> Line:
    return Line(desc, Decimal(str(qty)), unit, Decimal(str(price)), Decimal(rate), sku)


@dataclass
class Invoice:
    number: str
    sup: str
    date: dt.date
    lines: list[Line]
    po: str | None = None  # PO key (resolved to a number after numbering)
    dn: str | None = None  # DN number
    vessel: str | None = None
    customer: str = "AMS"
    kind: str = "invoice"  # invoice | credit_note
    ref_invoice: str | None = None
    deposit: Decimal = D(0)
    stated_vat: Decimal | None = None  # VAT as printed when it differs from the correct amount
    omit: set = field(default_factory=set)  # mandatory mentions missing from the document
    stamp: str | None = None
    copy_mark: str | None = None
    scanned: bool = False
    received: dt.date | None = None
    in_corpus: bool = True
    notes: list[str] = field(default_factory=list)
    period: str | None = None
    booked: list[dt.date] = field(default_factory=list)  # booking dates in the purchase journal (2 = booked twice)

    @property
    def s(self) -> Supplier:
        return SUPPLIERS[self.sup]

    @property
    def due(self) -> dt.date:
        return self.date + dt.timedelta(days=self.s.terms)

    @property
    def sign(self) -> int:
        return -1 if self.kind == "credit_note" else 1

    def vat_by_rate(self) -> dict[Decimal, tuple[Decimal, Decimal]]:
        out: dict[Decimal, list[Decimal]] = {}
        for ln in self.lines:
            out.setdefault(ln.rate, []).append(ln.amount)
        return {r: (sum(v, D(0)), q2(sum(v, D(0)) * r)) for r, v in out.items()}

    @property
    def net(self) -> Decimal:
        return sum((ln.amount for ln in self.lines), D(0))

    @property
    def vat_correct(self) -> Decimal:
        return sum((v for _, v in self.vat_by_rate().values()), D(0))

    @property
    def vat(self) -> Decimal:  # as printed
        return self.stated_vat if self.stated_vat is not None else self.vat_correct

    @property
    def total(self) -> Decimal:  # as printed (gross, before deposit)
        return self.net + self.vat

    @property
    def payable(self) -> Decimal:  # amount the invoice asks to pay
        return self.total - self.deposit


@dataclass
class PO:
    key: str
    sup: str
    date: dt.date
    lines: list[Line]
    approver: str
    vessel: str
    requested_by: str = "ops"
    terms: str = ""
    notes: list[str] = field(default_factory=list)
    number: str = ""

    @property
    def net(self) -> Decimal:
        return sum((ln.amount for ln in self.lines), D(0))


@dataclass
class DN:
    number: str
    sup: str
    date: dt.date
    po: str | None
    items: list[tuple[str, Decimal, Decimal, str]]  # desc, ordered, delivered, unit
    vessel: str
    kind: str = "delivery"  # delivery | service
    signed_by: str = "Bosun A. Kowalski"
    scanned: bool = False
    remarks: str = ""


@dataclass
class Payment:
    date: dt.date
    amount: Decimal
    label: str  # as it appears on the bank statement
    payee: str  # supplier code or OUTSIDE_PAYEES key
    settles: list[tuple[str, Decimal]]  # (invoice number or "PO:<key>", amount)
    method: str = "SEPA"  # SEPA | DD
    ref: str = ""
    iban_used: str | None = None

    @property
    def payee_name(self) -> str:
        return SUPPLIERS[self.payee].name if self.payee in SUPPLIERS else OUTSIDE_PAYEES[self.payee]["name"]

    @property
    def iban(self) -> str:
        if self.iban_used:
            return self.iban_used
        return SUPPLIERS[self.payee].iban if self.payee in SUPPLIERS else OUTSIDE_PAYEES[self.payee]["iban"]

    @property
    def bic(self) -> str:
        if self.iban_used == LME_NEW_IBAN:
            return LME_NEW_BIC
        return SUPPLIERS[self.payee].bic if self.payee in SUPPLIERS else OUTSIDE_PAYEES[self.payee]["bic"]


@dataclass
class BankLine:
    date: dt.date
    label: str
    debit: Decimal = D(0)
    credit: Decimal = D(0)
    category: str = "supplier"  # supplier | outside | payroll | social | tax | fees | customer
    payment: Payment | None = None
    detail: str = ""

    @property
    def vdate(self) -> dt.date:
        if self.credit:
            nd = self.date + dt.timedelta(days=1)
            while nd.weekday() >= 5:
                nd += dt.timedelta(days=1)
            return nd
        return self.date


@dataclass
class World:
    invoices: list[Invoice]
    pos: dict[str, PO]
    dns: list[DN]
    payments: list[Payment]
    bank: list[BankLine]
    opening_bank: Decimal

    def inv(self, number: str) -> Invoice:
        found = [i for i in self.invoices if i.number == number]
        assert len(found) == 1, number
        return found[0]

    def dn(self, number: str) -> DN:
        return next(d for d in self.dns if d.number == number)

    def po_of(self, inv: Invoice) -> PO | None:
        return self.pos.get(inv.po) if inv.po else None


# ---------------------------------------------------------------- the data

def build_world() -> World:
    inv: list[Invoice] = []
    pos: dict[str, PO] = {}
    dns: list[DN] = []
    pay: list[Payment] = []

    def add_po(key, sup, d, lines, approver, vessel, terms="", notes=(), requested_by="ops"):
        pos[key] = PO(key, sup, d, lines, approver, vessel, requested_by, terms, list(notes))

    def add_dn(number, sup, d, po, items, vessel, **kw):
        dns.append(DN(number, sup, d, po, items, vessel, **kw))

    def add_inv(**kw):
        i = Invoice(**kw)
        if not i.booked and i.customer == "AMS" and (i.received or i.date) <= date(30, 9):
            i.booked = [i.received or i.date]
        inv.append(i)
        return i

    def items(lines):
        return [(ln.desc, ln.qty, ln.qty, ln.unit) for ln in lines]

    A, S, B = "AURELIA", "SELENE", "BLUE"

    # ---------------- Mediterra Marine Supplies
    l312 = [L("Lube oil SAE 15W-40, 208 L drum", 4, "drum", "742.00", sku="LO-1540-208"),
            L("Fuel filter element FF-5320", 20, "pc", "38.50", sku="FF-5320"),
            L("Delivery and handling", 1, "lot", "320.00", sku="SRV-DEL")]
    add_po("med_jul", "MED", date(6, 7), l312, "ops", A)
    add_dn("MMS-DN-26-0702", "MED", date(10, 7), "med_jul", items(l312[:2]), A)
    add_inv(number="INV-2026-0312", sup="MED", date=date(14, 7), lines=l312, po="med_jul", dn="MMS-DN-26-0702", vessel=A)

    l371 = [L("Fuel filter element FF-5320", 24, "pc", "38.50", sku="FF-5320"),
            L("Lube oil SAE 15W-40, 208 L drum", 6, "drum", "742.00", sku="LO-1540-208"),
            L("Coolant concentrate, 20 L", 12, "can", "64.50", sku="CC-20"),
            L("Impeller kit for raw-water pump", 10, "kit", "186.00", sku="IMP-17937"),
            L("Engine-room wipes, industrial (box of 500)", 20, "box", "37.00", sku="WP-500"),
            L("Oil absorbent pads (bale of 200)", 10, "bale", "58.00", sku="OAP-200"),
            L("Delivery and handling", 1, "lot", "320.00", sku="SRV-DEL")]
    add_po("med_aug", "MED", date(20, 8), l371, "fd", S)
    add_dn("MMS-DN-26-0815", "MED", date(25, 8), "med_aug", items(l371[:6]), S)
    add_inv(number="INV-2026-0371", sup="MED", date=date(28, 8), lines=l371, po="med_aug", dn="MMS-DN-26-0815",
            vessel=S, notes=["Payment may be made in two equal instalments within the agreed terms."])

    l418 = [L("Lube oil SAE 15W-40, 208 L drum", 8, "drum", "742.00", sku="LO-1540-208"),
            L("Fuel filter element FF-5320", 36, "pc", "38.50", sku="FF-5320"),
            L("Hydraulic oil ISO VG 46, 208 L drum", 3, "drum", "698.00", sku="HO-46-208"),
            L("Impeller kit for raw-water pump", 8, "kit", "186.00", sku="IMP-17937"),
            L("Coolant concentrate, 20 L", 12, "can", "64.50", sku="CC-20"),
            L("Oil absorbent pads (bale of 200)", 13, "bale", "58.00", sku="OAP-200"),
            L("Nitrile gloves (box of 100)", 4, "box", "12.00", sku="GL-N100"),
            L("Delivery and handling", 1, "lot", "320.00", sku="SRV-DEL")]
    add_po("med_sep", "MED", date(21, 9), l418, "fd", A)
    add_dn("MMS-DN-26-0925", "MED", date(25, 9), "med_sep", items(l418[:7]), A)
    add_inv(number="INV-2026-0418", sup="MED", date=date(30, 9), lines=l418, po="med_sep", dn="MMS-DN-26-0925",
            vessel=A, received=date(2, 10), stamp="RECEIVED 02/10/2026", scanned=True, period="September 2026")

    # ---------------- SeaGlass Coatings
    l877 = [L("Antifouling Pro-X self-polishing, red, 2.5 L tin", 36, "tin", "155.00", "0", sku="PX-R-25"),
            L("Epoxy primer 2-pack, 5 L", 12, "set", "132.50", "0", sku="EP-2K-5"),
            L("Thinner No. 7, 5 L", 10, "can", "41.00", "0", sku="TH-7-5"),
            L("Application kit (rollers, trays, brushes)", 8, "kit", "60.00", "0", sku="AK-01"),
            L("Freight Genova - Monaco", 1, "lot", "400.00", "0", sku="FRT")]
    add_po("sea_aug", "SEA", date(5, 8), l877, "fd", B)
    add_dn("SG-DDT-2026/0641", "SEA", date(14, 8), "sea_aug", items(l877[:4]), B,
           remarks="4 tins PX-R-25 received dented, reserve noted on CMR")
    add_inv(number="SG-2026/0877", sup="SEA", date=date(18, 8), lines=l877, po="sea_aug", dn="SG-DDT-2026/0641",
            vessel=B)
    add_inv(number="SG-CN-2026/0112", sup="SEA", date=date(2, 9), kind="credit_note", ref_invoice="SG-2026/0877",
            lines=[L("Credit for 4 damaged tins Antifouling Pro-X red 2.5 L (reserve on CMR of 14/08/2026)", 4, "tin",
                     "155.00", "0", sku="PX-R-25")], po="sea_aug", vessel=B)

    # ---------------- Harbor Parts
    l1207 = [L("Shaft coupling bolt set, M16 (8 pcs)", 4, "set", "285.00", "0", sku="HP-CB16"),
             L("Cutless bearing 63 mm x 83 mm x 254 mm", 3, "pc", "486.00", "0", sku="HP-CL63"),
             L("Zinc anode set (shaft and rudder)", 15, "set", "37.00", "0", sku="HP-ZA"),
             L("Freight DAP Monaco", 1, "lot", "62.00", "0", sku="FRT")]
    add_po("har_jul", "HAR", date(1, 7), l1207, "ops", S, terms="14 days net from invoice date")
    add_dn("HP-DN-26-0712", "HAR", date(8, 7), "har_jul", items(l1207[:3]), S)
    add_inv(number="HP-26-1207", sup="HAR", date=date(9, 7), lines=l1207, po="har_jul", dn="HP-DN-26-0712", vessel=S)

    l1450 = [L("Shaft seal kit, 63 mm, dripless", 2, "kit", "1145.00", "0", sku="HP-SS63"),
             L("Cutless bearing 63 mm x 83 mm x 254 mm", 2, "pc", "486.00", "0", sku="HP-CL63"),
             L("Raw-water pump overhaul kit", 3, "kit", "412.00", "0", sku="HP-RWK"),
             L("Zinc anode set (shaft and rudder)", 6, "set", "37.00", "0", sku="HP-ZA"),
             L("Freight DAP Monaco", 1, "lot", "150.00", "0", sku="FRT")]
    add_po("har_sep", "HAR", date(1, 9), l1450, "ops", S, terms="14 days net from invoice date")
    add_dn("HP-DN-26-0931", "HAR", date(11, 9), "har_sep", items(l1450[:4]), S, scanned=True)
    add_inv(number="HP-26-1450", sup="HAR", date=date(12, 9), lines=l1450, po="har_sep", dn="HP-DN-26-0931", vessel=S)

    # ---------------- Marina Fuel Services
    for key, d_po, d_dn, d_inv, num, bdn, litres, vessel, appr in [
        ("mfs_jul", date(8, 7), date(13, 7), date(14, 7), "INV-2026-0968", "MFS-BDN-26-0713", 8250, A, "fd"),
        ("mfs_aug", date(6, 8), date(10, 8), date(11, 8), "INV-2026-1074", "MFS-BDN-26-0810", 6500, S, "fd"),
        ("mfs_sep", date(4, 9), date(11, 9), date(12, 9), "INV-2026-1182", "MFS-BDN-26-0911", 11000, A, "ceo"),
    ]:
        lines = [L(f"Marine gasoil (MGO) DMA, ISO 8217, delivered by truck, BDN {bdn}", litres, "L", "2.000",
                   sku="MGO-DMA")]
        add_po(key, "MFS", d_po, lines, appr, vessel, terms="30 days net from invoice date",
               notes=["Single delivery by road tanker at Quai Antoine Ier."])
        add_dn(bdn, "MFS", d_dn, key, items(lines), vessel, signed_by="Chief Eng. R. Lindqvist")
        add_inv(number=num, sup="MFS", date=d_inv, lines=lines, po=key, dn=bdn, vessel=vessel)

    # ---------------- Oceanic Safety Europe
    l552 = [L("Liferaft 12-person SOLAS A-pack, service exchange", 1, "pc", "2950.00", "0", sku="LR-12A"),
            L("EPIRB battery and hydrostatic release unit replacement", 2, "set", "385.00", "0", sku="EP-BHR"),
            L("Lifejacket SOLAS 150N with light", 20, "pc", "89.00", "0", sku="LJ-150"),
            L("Fire extinguisher 6 kg foam, MED approved", 6, "pc", "75.00", "0", sku="FE-6F"),
            L("Pyrotechnics set (rockets, hand flares, smoke signal)", 1, "set", "250.00", "0", sku="PY-SET")]
    add_po("ose_aug", "OSE", date(21, 8), l552, "fd", A, terms="30 days net from invoice date")
    add_dn("OSE-LS-26-0907", "OSE", date(7, 9), "ose_aug", items(l552), A)
    add_inv(number="INV-2026-552", sup="OSE", date=date(12, 9), lines=l552, po="ose_aug", dn="OSE-LS-26-0907",
            vessel=A)

    # ---------------- Northstar Yacht Services
    add_po("nys_jun", "NYS", date(5, 6), [L("Révision groupe électrogène 27 kW (forfait)", 1, "forfait", "1900.00")],
           "ops", B)
    add_inv(number="NYS-2026-071", sup="NYS", date=date(12, 6),
            lines=[L("Révision groupe électrogène 27 kW (forfait)", 1, "forfait", "1900.00")], po="nys_jun",
            vessel=B, booked=[date(12, 6)])
    add_inv(number="NYS-2026-114", sup="NYS", date=date(9, 9), vessel=A,
            lines=[L("Pompe de cale 24 V 3700 GPH", 1, "u", "1240.00", sku="PC-3700"),
                   L("Main-d'œuvre technicien (intervention du 06/09/2026)", 14, "h", "95.00"),
                   L("Forfait déplacement week-end", 1, "forfait", "380.00")],
            notes=["Intervention d'urgence : remplacement de la pompe de cale principale."])

    # ---------------- Côte d'Azur Ship Chandlers
    l788 = [L("Cordage polyester 14 mm (bobine 100 m)", 2, "u", "310.00"),
            L("Défenses cylindriques F6", 4, "u", "145.00"), L("Livraison quai", 1, "forfait", "250.00"),
            L("Produit nettoyant pont teck 5 L", 4, "u", "38.50"), L("Éponges et brosses pont (lot)", 1, "lot", "16.00")]
    add_po("cas_jul", "CAS", date(3, 7), l788, "ops", B)
    add_dn("BL-26-0706", "CAS", date(6, 7), "cas_jul", items(l788), B)
    add_inv(number="FA-2026-0788", sup="CAS", date=date(7, 7), lines=l788, po="cas_jul", dn="BL-26-0706", vessel=B)
    l851 = [L("Cordage polyamide 18 mm (bobine 50 m)", 2, "u", "395.00"), L("Manilles inox 12 mm", 20, "u", "18.50"),
            L("Produit nettoyant pont teck 5 L", 12, "u", "38.50"), L("Livraison quai", 1, "forfait", "68.00"),
            L("Gants de manutention (lot de 12)", 5, "lot", "42.00")]
    add_po("cas_aug", "CAS", date(3, 8), l851, "ops", A)
    add_dn("BL-26-0805", "CAS", date(5, 8), "cas_aug", items(l851), A)
    add_inv(number="FA-2026-0851", sup="CAS", date=date(6, 8), lines=l851, po="cas_aug", dn="BL-26-0805", vessel=A)
    l917 = [L("Cordage polyester 14 mm (bobine 100 m)", 2, "u", "310.00"), L("Défenses cylindriques F6", 6, "u", "145.00"),
            L("Produit nettoyant pont teck 5 L", 10, "u", "38.50"), L("Gants de manutention (lot de 12)", 5, "lot", "42.00"),
            L("Livraison quai", 1, "forfait", "300.00")]
    add_po("cas_sep", "CAS", date(28, 8), l917, "ops", A)
    add_dn("BL-26-0902", "CAS", date(2, 9), "cas_sep", items(l917[:4]), A)
    add_inv(number="FA-2026-0917", sup="CAS", date=date(3, 9), lines=l917, po="cas_sep", dn="BL-26-0902", vessel=A,
            booked=[date(3, 9), date(22, 9)])
    # duplicate copy sent with the reminder of 21/09 (same invoice, stamped DUPLICATA) -> separate document
    l948 = [L("Bidons huile 2T 1 L", 24, "u", "14.50"), L("Seaux inox 10 L", 6, "u", "48.00"),
            L("Ruban adhésif marine (lot de 10)", 4, "lot", "52.00"), L("Livraison quai", 1, "forfait", "512.00")]
    add_po("cas_sep2", "CAS", date(17, 9), l948, "ops", S)
    add_dn("BL-26-0923", "CAS", date(23, 9), "cas_sep2", items(l948[:3]), S)
    add_inv(number="FA-2026-0948", sup="CAS", date=date(24, 9), lines=l948, po="cas_sep2", dn="BL-26-0923", vessel=S)
    add_inv(number="FA-2026-0931", sup="CAS", date=date(15, 9), customer="AMC",
            lines=[L("Avitaillement pont – charter week 38 (forfait)", 1, "forfait", "1640.00"),
                   L("Livraison Port Vauban", 1, "forfait", "400.00")])

    # ---------------- Liguria Marine Electronics
    l498 = [L("AIS transponder class B, exchange unit", 1, "pc", "1480.00", "0", sku="AIS-B"),
            L("VHF antenna 2.4 m with mount", 2, "pc", "640.00", "0", sku="VHF-24"),
            L("Shipping & insurance", 1, "lot", "200.00", "0", sku="SHP")]
    add_po("lme_jun", "LME", date(24, 6), l498, "ops", B)
    add_dn("LME-DDT-26-0701", "LME", date(1, 7), "lme_jun", items(l498[:2]), B)
    add_inv(number="LME-26-0498", sup="LME", date=date(3, 7), lines=l498, po="lme_jun", dn="LME-DDT-26-0701", vessel=B)
    l611 = [L("Radar magnetron service kit", 1, "kit", "2780.00", "0", sku="RDR-MAG"),
            L("Multifunction display 16 in, exchange unit", 1, "pc", "1950.00", "0", sku="MFD-16X"),
            L("NMEA 2000 backbone kit", 3, "kit", "150.00", "0", sku="N2K-BB"),
            L("Shipping & insurance", 1, "lot", "300.00", "0", sku="SHP")]
    add_po("lme_aug", "LME", date(27, 8), l611, "fd", A)
    add_dn("LME-DDT-26-0831", "LME", date(31, 8), "lme_aug", items(l611[:3]), A)
    add_inv(number="LME-26-0611", sup="LME", date=date(1, 9), lines=l611, po="lme_aug", dn="LME-DDT-26-0831", vessel=A)

    # ---------------- Provence Hydraulique
    l1730 = [L("Vérin hydraulique passerelle (échange standard)", 1, "u", "1260.00"),
             L("Joints et kit d'étanchéité", 1, "lot", "250.00")]
    add_po("prh_jun", "PRH", date(30, 6), l1730, "ops", S)
    add_dn("BL-PH-26-0958", "PRH", date(7, 7), "prh_jun", items(l1730), S)
    add_inv(number="F26-01730", sup="PRH", date=date(8, 7), lines=l1730, po="prh_jun", dn="BL-PH-26-0958", vessel=S)
    l2214 = [L("Flexible hydraulique HP 1/2 - 2 m, embouts sertis", 40, "u", "68.50", sku="FHP-12-2"),
             L("Raccord droit JIC 1/2", 12, "u", "24.00", sku="RJ-12")]
    add_po("prh_sep", "PRH", date(2, 9), l2214, "ops", S)
    add_dn("BL-PH-26-1187", "PRH", date(10, 9), "prh_sep",
           [(l2214[0].desc, D(40), D(36), "u"), (l2214[1].desc, D(12), D(12), "u")], S,
           remarks="Reliquat : 4 flexibles FHP-12-2 à livrer semaine 41")
    add_inv(number="F26-02214", sup="PRH", date=date(11, 9), lines=l2214, po="prh_sep", dn="BL-PH-26-1187", vessel=S)

    # ---------------- Riviera Electronics (contractual deposit)
    l733 = [L("Système de vidéosurveillance IP – kit 8 caméras", 1, "kit", "6800.00", sku="CCTV-8IP"),
            L("Enregistreur NVR 16 voies 8 To", 1, "u", "2150.00", sku="NVR-16"),
            L("Câblage marine et connectique (forfait)", 1, "forfait", "1850.00"),
            L("Installation et paramétrage (journée technicien)", 4, "j", "850.00")]
    add_po("rve_aug", "RVE", date(25, 8), l733, "fd", A,
           terms="30% deposit of the gross amount payable on order; balance 30 days from invoice date",
           notes=["Supplier quote DEV-RE-2026-0457 accepted.", "Deposit invoice not required: the deposit is deducted on the final invoice."])
    add_dn("RE-BL-2026-0516", "RVE", date(16, 9), "rve_aug", items(l733[:3]), A)
    add_inv(number="RE-2026-0733", sup="RVE", date=date(17, 9), lines=l733, po="rve_aug", dn="RE-BL-2026-0516",
            vessel=A, deposit=D("5112.00"))

    # ---------------- Monaco Rigging & Sails
    l211 = [L("Halyard replacement, Dyneema 12 mm", 3, "pc", "450.00"), L("Rigger labour", 8, "h", "87.50")]
    add_po("mrs_jul", "MRS", date(6, 7), l211, "ops", B)
    add_dn("MRS-SR-26-0715", "MRS", date(15, 7), "mrs_jul", items(l211), B, kind="service", signed_by="Bosun A. Kowalski")
    add_inv(number="MRS-2026-0211", sup="MRS", date=date(17, 7), lines=l211, po="mrs_jul", dn="MRS-SR-26-0715", vessel=B)
    l298 = [L("Standing rigging survey and report", 1, "lot", "950.00"),
            L("Shroud and stay replacement, 1x19 compacted strand", 4, "pc", "1250.00"),
            L("Rigger labour", 16, "h", "87.50")]
    add_po("mrs_sep", "MRS", date(15, 9), l298, "fd", S)
    add_dn("MRS-SR-26-0924", "MRS", date(24, 9), "mrs_sep", items(l298), S, kind="service",
           signed_by="Marco Ferri, Chief Engineer")
    add_inv(number="MRS-2026-0298", sup="MRS", date=date(29, 9), lines=l298, po="mrs_sep", dn="MRS-SR-26-0924",
            vessel=S, received=date(6, 10), stamp="RECEIVED 06 OCT 2026", period="works completed 24/09/2026")

    # ---------------- Var Pneumatique (goods received, invoice not received)
    lvp = [L("Compresseur d'air haute pression 300 bar, 2,2 kW", 2, "u", "1960.00", sku="CHP-300")]
    add_po("vpn_sep", "VPN", date(18, 9), lvp, "ops", S)
    add_dn("VP-BL-26-0544", "VPN", date(28, 9), "vpn_sep", items(lvp), S, scanned=True)

    # ---------------- Sud Marine Électricité (VAT arithmetic error)
    l322 = [L("Remplacement disjoncteurs tableau 230 V", 1, "forfait", "2250.00"), L("Main-d'œuvre électricien", 16, "h", "75.00")]
    add_po("sme_jul", "SME", date(13, 7), l322, "ops", B)
    add_dn("SME-FI-26-0718", "SME", date(18, 7), "sme_jul", items(l322), B, kind="service")
    add_inv(number="SME-26-0322", sup="SME", date=date(21, 7), lines=l322, po="sme_jul", dn="SME-FI-26-0718", vessel=B)
    l457 = [L("Remplacement tableau électrique 24 V", 1, "forfait", "4850.00"),
            L("Chargeur de batteries 24 V 100 A", 1, "u", "1690.00"),
            L("Câbles et protections (forfait)", 1, "forfait", "980.00"),
            L("Main-d'œuvre électricien", 24, "h", "75.00")]
    add_po("sme_sep", "SME", date(7, 9), l457, "fd", S)
    add_dn("SME-FI-26-0911", "SME", date(11, 9), "sme_sep", items(l457), S, kind="service",
           signed_by="Marco Ferri, Chief Engineer")
    add_inv(number="SME-26-0457", sup="SME", date=date(14, 9), lines=l457, po="sme_sep", dn="SME-FI-26-0911",
            vessel=S, stated_vat=D("1846.00"))

    # ---------------- Quick Marine Repairs (non-compliant invoice, no PO)
    add_dn("QMR-SR-0911", "QMR", date(11, 9), None,
           [("Emergency hull dive inspection and propeller clearing (fishing net)", D(1), D(1), "job")], S,
           kind="service", signed_by="Marco Ferri, Chief Engineer", scanned=True)
    add_inv(number="QMR 0912", sup="QMR", date=date(12, 9), vessel=S,
            lines=[L("Emergency hull dive inspection and propeller clearing, M/Y Selene, 11/09/2026", 1, "job",
                     "1400.00")],
            omit={"supplier_address", "supplier_vat", "customer_address", "vat_breakdown", "due_date"})

    # ---------------- NavTech Systems (PO above the Finance Director's limit)
    l877n = [L("ECDIS software maintenance 01/10/2026-30/09/2027 (per vessel)", 3, "vessel", "5900.00", "0", sku="ECM-12"),
             L("Chart data subscription, global coverage, 12 months", 1, "lic", "6800.00", "0", sku="CDS-G12")]
    add_po("nts_sep", "NTS", date(8, 9), l877n, "fd", "FLEET", terms="30 days net from invoice date")
    add_inv(number="NT-2026-31877", sup="NTS", date=date(15, 9), lines=l877n, po="nts_sep", vessel="FLEET",
            period="01/10/2026 - 30/09/2027")

    # ---------------- EcoMarine Waste Services
    for num, d in [("ECO-26-0871", date(20, 7)), ("ECO-26-0979", date(20, 8)), ("ECO-26-1101", date(24, 9))]:
        add_inv(number=num, sup="ECO", date=d, vessel="FLEET",
                lines=[L("Collecte huiles usagées et filtres – forfait mensuel (contrat CT-2024-118)", 1, "forfait", "640.00")])
    l1093 = [L("Pompage et traitement eaux de cale", 12, "m3", "210.00"),
             L("Nettoyage des caisses à combustible (forfait)", 1, "forfait", "2480.00"),
             L("Élimination déchets huileux", "1.6", "t", "400.00")]
    add_po("eco_sep", "ECO", date(14, 9), l1093, "ops", S)
    add_dn("ECO-BSD-26-0921", "ECO", date(21, 9), "eco_sep", items(l1093), S, kind="service")
    add_inv(number="ECO-26-1093", sup="ECO", date=date(22, 9), lines=l1093, po="eco_sep", dn="ECO-BSD-26-0921", vessel=S)

    # ---------------- contract suppliers (no PO)
    for m in (7, 8, 9):
        add_inv(number=f"MBM-2026-{m:02d}14", sup="MBM", date=date(1, m), vessel=A,
                lines=[L(f"Berth fee B-14, Quai Antoine Ier, M/Y Aurelia (52 m) – {dt.date(2026, m, 1):%B %Y}", 1,
                         "month", "4800.00")])
        add_inv(number=f"MBM-2026-{m:02d}07", sup="MBM", date=date(1, m), vessel=S,
                lines=[L(f"Berth fee C-07, Quai Antoine Ier, M/Y Selene (38 m) – {dt.date(2026, m, 1):%B %Y}", 1,
                         "month", "3900.00")])
    for m, net in [(7, "1070.30"), (8, "1080.93"), (9, "1070.30")]:
        add_inv(number=f"RT-{m:02d}26-1187{30 + m}", sup="RTL", date=date(1, m),
                lines=[L(f"Fixed lines, fibre 1 Gb/s and mobile fleet (14 lines) – {dt.date(2026, m, 1):%B %Y}", 1,
                         "month", net)])
    for m in (7, 8, 9):
        add_inv(number=f"KIT-2026-{m:02d}01", sup="KIT", date=date(1, m),
                lines=[L(f"Managed IT services, office + 3 vessels – {dt.date(2026, m, 1):%B %Y}", 1, "month", "2450.00")])
    add_inv(number="KIT-2026-0602", sup="KIT", date=date(1, 6), booked=[date(1, 6)],
            lines=[L("Additional engineering hours – server migration (May 2026)", 11, "h", "100.00")])
    for m in (7, 8, 9):
        add_inv(number=f"ACS-26-{m:02d}25", sup="ACS", date=date(25, m),
                lines=[L(f"Nettoyage bureaux 7 Quai Antoine Ier – {['juillet', 'août', 'septembre'][m - 7]} 2026", 1,
                         "forfait", "980.00")])
    add_inv(number="LIB-26-2981", sup="LIB", date=date(1, 7), vessel="FLEET",
            lines=[L("Hull & machinery premium, policy HM-2026-0441, Q3 2026 instalment", 1, "qtr", "18750.00", "0")])
    add_inv(number="LIB-26-3317", sup="LIB", date=date(12, 9), vessel=S,
            lines=[L("Additional P&I premium – crew increase M/Y Selene, policy PI-2026-0213", 1, "lot", "2140.00", "0")])
    for num, d, desc, amt in [("CL-26-3980", date(15, 7), "Placement fee – Deckhand, M/Y Aurelia", "2400.00"),
                              ("CL-26-4105", date(5, 8), "Placement fee – Stewardess, M/Y Aurelia", "2400.00"),
                              ("CL-26-4410", date(3, 9), "Placement fee – Second Engineer, M/Y Selene", "3600.00"),
                              ("CL-26-4452", date(19, 9), "Crew travel arrangements and visa processing (4 crew)", "1850.00")]:
        add_inv(number=num, sup="CRW", date=d, lines=[L(desc, 1, "lot", amt, "0")])

    def lmp(num, d, food, bev, booked_ok=True, in_corpus=True):
        lines = [L("Fruits et légumes frais", 1, "lot", food[0], "0.055"), L("Viandes et poissons", 1, "lot", food[1], "0.055"),
                 L("Épicerie fine et produits secs", 1, "lot", food[2], "0.055"),
                 L("Vins et spiritueux", 1, "lot", bev[0], "0.20"), L("Eaux minérales et boissons sans alcool", 1, "lot", bev[1], "0.20")]
        add_inv(number=num, sup="LMP", date=d, lines=lines, in_corpus=in_corpus)

    lmp("LMP-26-0988", date(6, 7), ("512.30", "980.40", "260.00"), ("760.00", "142.00"))
    lmp("LMP-26-1041", date(20, 7), ("488.10", "1104.70", "199.50"), ("515.00", "118.00"))
    lmp("LMP-26-1093", date(3, 8), ("601.80", "1260.00", "305.20"), ("880.00", "164.00"))
    lmp("LMP-26-1137", date(17, 8), ("455.25", "940.60", "210.00"), ("430.00", "96.00"))
    lmp("LMP-26-1166", date(28, 8), ("530.00", "1012.40", "244.80"), ("610.00", "128.00"))
    lmp("LMP-26-1204", date(4, 9), ("642.40", "1185.60", "318.00"), ("920.00", "186.00"))
    lmp("LMP-26-1251", date(16, 9), ("580.20", "1046.00", "248.00"), ("402.00", "138.00"))
    lmp("LMP-26-1297", date(26, 9), ("410.00", "722.00", "188.00"), ("296.00", "114.00"), in_corpus=False)

    # ---------------- PO numbering (chronological)
    for n, po in enumerate(sorted(pos.values(), key=lambda p: (p.date, p.key)), start=318):
        po.number = f"PO-2026-{n:04d}"

    # ---------------- payments
    w = World(inv, pos, dns, pay, [], D("412560.18"))

    def p(d, invno_or_amt, label, payee=None, settles=None, **kw):
        if isinstance(invno_or_amt, str):
            i = w.inv(invno_or_amt)
            amt = i.payable
            settles = settles or [(i.number, amt)]
            payee = payee or i.sup
        else:
            amt = invno_or_amt
        assert d.weekday() < 5, (d, label)
        pay.append(Payment(d, amt, label, payee, settles or [], **kw))

    # direct debits of contract suppliers
    for i in inv:
        if i.sup in ("MBM", "RTL", "KIT") and i.date.month >= 7:
            dd = prev_business_day(i.date + dt.timedelta(days=9 if i.sup in ("MBM", "KIT") else 14))
            p(dd, i.number, f"PRLV SEPA {i.s.short} {i.number}", method="DD", ref=i.number)
    # transfers: routine invoices paid at due date (previous business day), except items left open on purpose
    left_open = {"CL-26-3980", "ECO-26-0871", "KIT-2026-0602", "NYS-2026-071"}
    special = {"INV-2026-0371", "SG-2026/0877", "SG-CN-2026/0112", "HP-26-1450", "INV-2026-1182", "NYS-2026-114",
               "FA-2026-0917", "LME-26-0611", "QMR 0912", "RE-2026-0733", "LIB-26-3317", "FA-2026-0931"}
    for i in inv:
        if i.sup in ("MBM", "RTL", "KIT") or i.number in left_open or i.number in special or i.customer != "AMS":
            continue
        d = prev_business_day(i.due)
        if d <= date(9, 10) and i.date >= date(1, 7):
            p(d, i.number, f"VIR SEPA EMIS {i.s.short} {i.number}", ref=i.number)
    # September specific cases
    p(date(2, 9), D("5112.00"), f"VIR SEPA EMIS RIVIERA ELECTRONICS ACOMPTE 30% {pos['rve_aug'].number}", "RVE",
      [("RE-2026-0733", D("5112.00"))], ref=f"ACOMPTE {pos['rve_aug'].number}")
    p(date(4, 9), D("4870.00"), "VIR SEPA EMIS HARBOR PARTS BV INV HP-26-1450", "HAR", [("HP-26-1450", D("4870.00"))],
      ref="HP-26-1450")
    p(date(10, 9), D("5790.00"), "VIR SEPA EMIS MEDITERRA MARINE SUPPL INV-2026-0371 1/2", "MED",
      [("INV-2026-0371", D("5790.00"))], ref="INV-2026-0371 1/2")
    p(date(15, 9), D("7830.00"), "VIR SEPA EMIS SEAGLASS COATINGS SRL SG-2026/0877 LESS CN0112", "SEA",
      [("SG-2026/0877", D("7830.00"))], ref="SG-2026/0877 LESS CN0112")
    p(date(18, 9), D("5480.00"), "VIR SEPA EMIS LIGURIA MARINE ELECTR LME-26-0611", "LME", [("LME-26-0611", D("5480.00"))],
      ref="LME-26-0611", iban_used=LME_NEW_IBAN)
    p(date(18, 9), "QMR 0912", "VIR SEPA EMIS QUICK MARINE REPAIRS QMR 0912", ref="QMR 0912")
    p(date(22, 9), D("13200.00"), "VIR SEPA EMIS MARINA FUEL SERVICES INV 1182", "MFS", [("INV-2026-1182", D("13200.00"))],
      ref="INV 1182")
    p(date(23, 9), D("3540.00"), "VIR SEPA EMIS NORTHSTAR YACHT SERV NYS-2026-114", "NYS", [("NYS-2026-114", D("3540.00"))],
      ref="NYS-2026-114")
    p(date(24, 9), D("5790.00"), "VIR SEPA EMIS MEDITERRA MARINE SUPPL INV-2026-0371 2/2", "MED",
      [("INV-2026-0371", D("5790.00"))], ref="INV-2026-0371 2/2")
    p(date(25, 9), D("2862.00"), "VIR SEPA EMIS COTE D AZUR SHIP CHAND FA-2026-0917", "CAS", [("FA-2026-0917", D("2862.00"))],
      ref="FA-2026-0917")
    p(date(25, 9), D("2140.00"), "VIR SEPA EMIS LIGHTHOUSE INSURANCE LIB-26-3317", "LIB", [("LIB-26-3317", D("2140.00"))],
      ref="LIB-26-3317")
    p(date(25, 9), D("3750.00"), "VIR SEPA EMIS MISC REF 0925-77", "DUBOIS", [], ref="MISC REF 0925-77")
    p(date(29, 9), D("1980.00"), "VIR SEPA EMIS BLUEWATER CONSULTING CONSULTING SEPT 2026", "BLUEWATER", [],
      ref="CONSULTING SEPT 2026")
    for x in pay:  # consistency: settled amounts add up to the payment
        if x.settles:
            assert sum(a for _, a in x.settles) == x.amount, x

    # ---------------- bank statement lines
    bank = w.bank
    for x in pay:
        bank.append(BankLine(x.date, x.label, debit=x.amount, category="supplier" if x.payee in SUPPLIERS else "outside",
                             payment=x))
    for m, d_rec in [(7, date(6, 7)), (8, date(5, 8)), (9, date(7, 9)), (10, date(5, 10))]:
        bank.append(BankLine(d_rec, f"VIR SEPA RECU AURELIA YACHTING LTD MGMT FEE AMS-2026-{m:02d}01", credit=D("48000.00"),
                             category="customer"))
        bank.append(BankLine(d_rec, f"VIR SEPA RECU SELENE MARINE HOLDINGS MGMT FEE AMS-2026-{m:02d}02", credit=D("31500.00"),
                             category="customer"))
        bank.append(BankLine(prev_business_day(d_rec + dt.timedelta(days=3)),
                             f"VIR SEPA RECU BLUE HORIZON YACHTS SA MGMT FEE AMS-2026-{m:02d}03", credit=D("22750.00"),
                             category="customer"))
    for d_rec, who, ref, amt in [(date(16, 7), "AURELIA YACHTING LTD", "RECHARGE AMS-2026-0711", "36418.20"),
                                 (date(14, 8), "SELENE MARINE HOLDINGS", "RECHARGE AMS-2026-0812", "18904.75"),
                                 (date(17, 9), "AURELIA YACHTING LTD", "RECHARGE AMS-2026-0911", "41275.60"),
                                 (date(24, 9), "BLUE HORIZON YACHTS SA", "RECHARGE AMS-2026-0913", "9862.30")]:
        bank.append(BankLine(d_rec, f"VIR SEPA RECU {who} {ref}", credit=D(amt), category="customer"))
    for d, amt in [(date(30, 7), "84910.20"), (date(28, 8), "85377.65"), (date(30, 9), "86420.55")]:
        bank.append(BankLine(d, f"VIR SEPA EMIS SALAIRES {d:%m}/2026 (LISTE 42 BENEFICIAIRES)", debit=D(amt), category="payroll"))
    for d, amt in [(date(15, 7), "30944.10"), (date(14, 8), "31102.35"), (date(15, 9), "31862.40")]:
        bank.append(BankLine(d, f"PRLV SEPA COTISATIONS SOCIALES {(d.month - 1):02d}/2026", debit=D(amt), category="social"))
    for d, amt in [(date(20, 7), "12418.00"), (date(20, 8), "13906.00"), (date(21, 9), "14215.00")]:
        bank.append(BankLine(d, f"PAIEMENT TVA {(d.month - 1):02d}/2026 DECLARATION CA3", debit=D(amt), category="tax"))
    for d in (date(31, 7), date(31, 8), date(30, 9)):
        bank.append(BankLine(d, "FRAIS TENUE DE COMPTE", debit=D("45.00"), category="fees"))
        bank.append(BankLine(d, "ABONNEMENT BANQUE EN LIGNE PRO", debit=D("18.00"), category="fees"))
    bank.append(BankLine(date(30, 9), "COMMISSIONS VIREMENTS SEPA 09/2026 (24 OPERATIONS)", debit=D("12.00"), category="fees"))
    bank.sort(key=lambda b: (b.date, 0 if b.credit else 1, b.label))
    return w


# ---------------------------------------------------------------- derived views used by documents and answers

def september_journal(w: World) -> list[tuple[str, dt.date, Invoice]]:
    """Purchase journal AC of September 2026: (piece, booking date, invoice); an invoice booked twice appears twice."""
    rows = [(d, i) for i in w.invoices if i.customer == "AMS" for d in i.booked if d.month == 9 and d.year == 2026]
    rows.sort(key=lambda r: (r[0], r[1].sup, r[1].number))
    return [(f"AC-2609-{n:03d}", d, i) for n, (d, i) in enumerate(rows, start=1)]


def journal(w: World, month: int) -> list[tuple[str, dt.date, Invoice]]:
    rows = [(d, i) for i in w.invoices if i.customer == "AMS" for d in i.booked if d.month == month and d.year == 2026]
    rows.sort(key=lambda r: (r[0], r[1].sup, r[1].number))
    return [(f"AC-26{month:02d}-{n:03d}", d, i) for n, (d, i) in enumerate(rows, start=1)]


def ledger_entries(w: World, sup: str) -> list[tuple[dt.date, str, str, Decimal, Decimal]]:
    """(date, piece, label, debit, credit) for a supplier account, all periods, in date order."""
    out = []
    for month in (6, 7, 8, 9):
        for piece, d, i in journal(w, month):
            if i.sup != sup:
                continue
            amt = i.total
            if i.kind == "credit_note":
                out.append((d, piece, f"Avoir {i.number}", amt, D(0)))
            else:
                out.append((d, piece, f"Facture {i.number}", D(0), amt))
    for x in w.payments:
        if x.payee == sup and x.date <= date(30, 9):
            out.append((x.date, f"BQ-26{x.date.month:02d}", f"Règlement {x.ref or x.label}", x.amount, D(0)))
    out.sort(key=lambda e: (e[0], e[1]))
    return out


def ledger_balance(w: World, sup: str, upto: dt.date) -> Decimal:
    """Credit balance (amount owed) of a supplier account at a date."""
    return sum((c - d for (dd, _, _, d, c) in ledger_entries(w, sup) if dd <= upto), D(0))


def open_items(w: World, at: dt.date) -> list[tuple[Invoice, Decimal, int]]:
    """Open purchase invoices at a date per the ledger (FIFO by invoice number): (invoice, open amount, booking index).

    An invoice booked twice gives two items: the payment clears the first booking only."""
    items = []
    for i in w.invoices:
        if i.customer != "AMS" or i.kind == "credit_note":
            continue
        for k, d in enumerate(i.booked):
            if d <= at:
                items.append([i, i.total, k])
    paid: dict[str, Decimal] = {}
    for x in w.payments:
        if x.date <= at:
            for num, a in x.settles:
                paid[num] = paid.get(num, D(0)) + a
    for i in w.invoices:  # credit notes reduce the invoice they refer to
        if i.kind == "credit_note" and i.booked and i.booked[0] <= at:
            paid[i.ref_invoice] = paid.get(i.ref_invoice, D(0)) + i.total
    out = []
    for i, amt, k in items:
        rem = amt
        take = min(paid.get(i.number, D(0)), rem)
        paid[i.number] = paid.get(i.number, D(0)) - take
        rem -= take
        if rem != 0:
            out.append((i, rem, k))
    return out
