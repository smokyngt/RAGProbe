"""PDF rendering of AccountingBench documents (reportlab, vector, fonts embedded).

Layout rules that keep the corpus machine-checkable: table cells never wrap (the font shrinks to fit), a label and its
value are always drawn on the same baseline, and every amount is printed with the issuer's own number format.
"""
from __future__ import annotations

import datetime as dt
import math
import random
from decimal import Decimal
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from common import D, fdate, fmt

_FONTS = {
    "Sans": "liberation/LiberationSans-Regular.ttf", "Sans-B": "liberation/LiberationSans-Bold.ttf",
    "Sans-I": "liberation/LiberationSans-Italic.ttf", "Serif": "liberation/LiberationSerif-Regular.ttf",
    "Serif-B": "liberation/LiberationSerif-Bold.ttf", "Serif-I": "liberation/LiberationSerif-Italic.ttf",
    "DV": "dejavu/DejaVuSans.ttf", "DV-B": "dejavu/DejaVuSans-Bold.ttf",
    "Mono": "liberation/LiberationMono-Regular.ttf", "Mono-B": "liberation/LiberationMono-Bold.ttf",
}
for _n, _f in _FONTS.items():
    pdfmetrics.registerFont(TTFont(_n, f"/usr/share/fonts/truetype/{_f}"))

GREY = HexColor("#5F6B7A")
LIGHT = HexColor("#EEF2F6")
RULE = HexColor("#C9D2DC")
NAVY = HexColor("#0D2C54")
TEAL = HexColor("#0FA3B1")
INK = HexColor("#1F3A93")
RED = HexColor("#B71C1C")


class NumberedCanvas(canvas.Canvas):
    """Canvas that knows the page count when it saves (for 'Page x of y')."""

    def __init__(self, *a, page_label=None, **kw):
        super().__init__(*a, **kw)
        self._states = []
        self._page_label = page_label

    def showPage(self):
        self._states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._states)
        for st in self._states:
            self.__dict__.update(st)
            if self._page_label:
                self._page_label(self, self._pageNumber, n)
            super().showPage()
        super().save()


class Doc:
    def __init__(self, path: Path, title: str, author: str, land: bool = False, page_label=None, creator="AMS DMS"):
        self.size = landscape(A4) if land else A4
        self.W, self.H = self.size
        self.c = NumberedCanvas(str(path), pagesize=self.size, page_label=page_label, pageCompression=1,
                                invariant=1)
        self.c.setTitle(title)
        self.c.setAuthor(author)
        self.c.setCreator(creator)
        self.c.setProducer(creator)

    # primitives
    def text(self, x, y, s, f="Sans", size=9, color=black, align="l", maxw=None):
        s = str(s)
        if maxw:
            while size > 6 and pdfmetrics.stringWidth(s, f, size) > maxw:
                size -= 0.25
            while len(s) > 4 and pdfmetrics.stringWidth(s, f, size) > maxw:
                s = s[:-2].rstrip() + "…"
        c = self.c
        c.setFont(f, size)
        c.setFillColor(color)
        if align == "r":
            c.drawRightString(x, y, s)
        elif align == "c":
            c.drawCentredString(x, y, s)
        else:
            c.drawString(x, y, s)

    def width(self, s, f="Sans", size=9):
        return pdfmetrics.stringWidth(str(s), f, size)

    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.5, r=0):
        c = self.c
        c.setLineWidth(lw)
        if fill is not None:
            c.setFillColor(fill)
        if stroke is not None:
            c.setStrokeColor(stroke)
        if r:
            c.roundRect(x, y, w, h, r, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        else:
            c.rect(x, y, w, h, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)

    def hline(self, x1, x2, y, color=RULE, lw=0.5):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(lw)
        self.c.line(x1, y, x2, y)

    def para(self, x, y, s, width, f="Sans", size=9, leading=None, color=black, bottom=None, on_break=None):
        """Word-wrapped paragraph; returns the y below it. Paragraph breaks on '\n'."""
        leading = leading or size * 1.35
        for block in str(s).split("\n"):
            words, line = block.split(" "), ""
            if not block:
                y -= leading
                continue
            for wd in words:
                trial = (line + " " + wd).strip()
                if self.width(trial, f, size) > width and line:
                    if bottom is not None and y < bottom and on_break:
                        y = on_break()
                    self.text(x, y, line, f, size, color)
                    y -= leading
                    line = wd
                else:
                    line = trial
            if line:
                if bottom is not None and y < bottom and on_break:
                    y = on_break()
                self.text(x, y, line, f, size, color)
                y -= leading
        return y

    def new_page(self):
        self.c.showPage()

    def save(self):
        self.c.showPage()
        self.c.save()

    # composite elements
    def table(self, x, y, cols, rows, head_fill=NAVY, head_color=white, f="Sans", fb="Sans-B", size=8, row_h=13,
              zebra=LIGHT, grid=None, head=True, bold_rows=(), bottom=40, on_break=None, head_size=None):
        """cols = [(title, width, align)], rows = [[str, ...]]; returns y below the table. Paginates via on_break."""
        total_w = sum(w for _, w, _ in cols)

        def draw_head(y):
            if not head:
                return y
            self.rect(x, y - row_h + 3, total_w, row_h, fill=head_fill)
            cx = x
            for title, w, al in cols:
                tx = cx + 3 if al == "l" else (cx + w - 3 if al == "r" else cx + w / 2)
                self.text(tx, y - row_h + 7, title, fb, head_size or size, head_color, al, maxw=w - 5)
                cx += w
            return y - row_h

        y = draw_head(y)
        for n, row in enumerate(rows):
            if y - row_h < bottom and on_break:
                y = draw_head(on_break())
            if zebra is not None and n % 2 == 1:
                self.rect(x, y - row_h + 3, total_w, row_h, fill=zebra)
            if grid is not None:
                self.hline(x, x + total_w, y - row_h + 3, grid, 0.4)
            cx = x
            font = fb if n in bold_rows else f
            for (title, w, al), val in zip(cols, row):
                tx = cx + 3 if al == "l" else (cx + w - 3 if al == "r" else cx + w / 2)
                self.text(tx, y - row_h + 7, val, font, size, black, al, maxw=w - 5)
                cx += w
            y -= row_h
        return y

    def kv(self, x, y, pairs, f="Sans", fb="Sans-B", size=8.5, gap=11.5, label_w=70, color=black, label_color=GREY):
        for k, v in pairs:
            self.text(x, y, k, f, size, label_color)
            self.text(x + label_w, y, v, fb, size, color)
            y -= gap
        return y

    def stamp(self, x, y, lines, color=RED, w=None):
        size = 10
        w = w or max(self.width(s, "Sans-B", size) for s in lines) + 16
        h = 8 + len(lines) * 13
        self.c.setStrokeColor(color)
        self.c.setLineWidth(1.6)
        self.c.roundRect(x, y, w, h, 4, stroke=1, fill=0)
        self.c.setLineWidth(0.6)
        self.c.roundRect(x + 2.5, y + 2.5, w - 5, h - 5, 3, stroke=1, fill=0)
        for k, s in enumerate(lines):
            self.text(x + w / 2, y + h - 15 - 13 * k, s, "Sans-B", size, color, "c")

    def signature(self, x, y, seed, w=90, color=INK):
        rnd = random.Random(seed)
        c = self.c
        c.setStrokeColor(color)
        c.setLineWidth(1.1)
        p = c.beginPath()
        px, py = x, y + rnd.uniform(4, 10)
        p.moveTo(px, py)
        for _ in range(7):
            nx = px + w / 7
            p.curveTo(px + rnd.uniform(0, 12), py + rnd.uniform(-14, 18), nx - rnd.uniform(0, 12),
                      py + rnd.uniform(-16, 16), nx, y + rnd.uniform(0, 14))
            px, py = nx, y + rnd.uniform(0, 14)
        c.drawPath(p, stroke=1, fill=0)
        c.line(x - 4, y - 3, x + w * 0.8, y - 1)

    def logo(self, x, y, kind, color, initials, size=34):
        c = self.c
        col = HexColor(color)
        c.setFillColor(col)
        c.setStrokeColor(col)
        s = size
        if kind in ("circle", "ring", "radar"):
            c.circle(x + s / 2, y + s / 2, s / 2, stroke=0, fill=1)
            if kind != "circle":
                c.setStrokeColor(white)
                c.setLineWidth(1.2)
                c.circle(x + s / 2, y + s / 2, s / 2 - 4, stroke=1, fill=0)
                if kind == "radar":
                    c.line(x + s / 2, y + s / 2, x + s - 6, y + s - 8)
        elif kind == "hex":
            p = c.beginPath()
            for k in range(6):
                a = math.pi / 3 * k + math.pi / 6
                px, py = x + s / 2 + s / 2 * math.cos(a), y + s / 2 + s / 2 * math.sin(a)
                p.moveTo(px, py) if k == 0 else p.lineTo(px, py)
            p.close()
            c.drawPath(p, stroke=0, fill=1)
        elif kind == "shield":
            p = c.beginPath()
            p.moveTo(x, y + s)
            p.lineTo(x + s, y + s)
            p.lineTo(x + s, y + s * 0.45)
            p.curveTo(x + s, y + s * 0.15, x + s * 0.6, y, x + s / 2, y)
            p.curveTo(x + s * 0.4, y, x, y + s * 0.15, x, y + s * 0.45)
            p.close()
            c.drawPath(p, stroke=0, fill=1)
        else:
            c.roundRect(x, y, s, s, s * 0.22, stroke=0, fill=1)
        c.setStrokeColor(white)
        c.setLineWidth(1.3)
        if kind == "wave":
            for k in (0, 1):
                p = c.beginPath()
                p.moveTo(x + 4, y + 8 + k * 5)
                p.curveTo(x + s * 0.35, y + 14 + k * 5, x + s * 0.65, y + 2 + k * 5, x + s - 4, y + 8 + k * 5)
                c.drawPath(p, stroke=1, fill=0)
        elif kind in ("anchor", "sail"):
            c.line(x + s / 2, y + 5, x + s / 2, y + 12)
            c.line(x + s / 2 - 6, y + 7, x + s / 2 + 6, y + 7)
        elif kind == "bolt":
            c.line(x + s * 0.55, y + 4, x + s * 0.4, y + 11)
            c.line(x + s * 0.4, y + 11, x + s * 0.6, y + 11)
        elif kind == "signal":
            for k in range(3):
                c.rect(x + 6 + k * 5, y + 5, 3, 4 + k * 3, stroke=0, fill=0)
        fs = s * (0.42 if len(initials) <= 2 else 0.32)
        self.text(x + s / 2, y + s / 2 - fs * 0.15 + (3 if kind in ("wave", "anchor", "sail", "bolt", "signal") else 0),
                  initials, "Sans-B", fs, white, "c")


def initials(name: str) -> str:
    skip = {"S.A.M.", "SAS", "SARL", "S.A.R.L.", "GmbH", "B.V.", "Ltd", "S.r.l.", "SA", "&", "du", "de", "la", "d'Azur"}
    words = [w for w in name.replace("'", " ").split() if w not in skip]
    return "".join(w[0] for w in words[:3]).upper()


# ---------------------------------------------------------------- labels

LBL = {
    "en": dict(invoice="INVOICE", credit_note="CREDIT NOTE", no="Invoice No.", cn_no="Credit note No.", date="Invoice date",
               cn_date="Credit note date", due="Due date", cust="Customer No.", po="Your PO", dn="Delivery note",
               vessel="Vessel", bill="Bill to", ship="Deliver to", item="Item", desc="Description", qty="Qty",
               unit="Unit", price="Unit price", vat="VAT", amount="Amount", net="Net total", total="TOTAL EUR",
               deposit="Less deposit received", topay="AMOUNT DUE EUR", pay="Payment details", ref="Payment reference",
               terms="Payment terms", days="{n} days net from invoice date", orig="Original invoice",
               rc="Reverse charge: VAT to be accounted for by the recipient (Art. 196 Directive 2006/112/EC).",
               exempt="VAT exempt: insurance transaction (Art. 135(1)(a) Directive 2006/112/EC).",
               vat_summary="VAT summary", base="Taxable base", rate="Rate", period="Service period"),
    "fr": dict(invoice="FACTURE", credit_note="AVOIR", no="Facture n°", cn_no="Avoir n°", date="Date de facture",
               cn_date="Date de l'avoir", due="Échéance", cust="Code client", po="Votre commande", dn="Bon de livraison",
               vessel="Navire", bill="Facturé à", ship="Livré à", item="Réf.", desc="Désignation", qty="Qté", unit="U",
               price="PU HT", vat="TVA", amount="Montant HT", net="Total HT", total="Total TTC",
               deposit="Acompte versé", topay="NET À PAYER EUR", pay="Règlement", ref="Référence à rappeler",
               terms="Conditions de paiement", days="{n} jours date de facture", orig="Facture d'origine",
               rc="Autoliquidation : TVA due par le preneur (art. 196 directive 2006/112/CE).",
               exempt="Exonération de TVA : opération d'assurance.",
               vat_summary="Récapitulatif TVA", base="Base HT", rate="Taux", period="Période"),
}
FR_LEGAL = ("En cas de retard de paiement : pénalités au taux de 3 fois le taux d'intérêt légal et indemnité forfaitaire "
            "pour frais de recouvrement de 40 € (art. L441-10 du Code de commerce). Pas d'escompte pour paiement anticipé.")


def pct(rate: Decimal, num: str) -> str:
    v = (rate * 100).normalize()
    s = f"{v:f}"
    return (s.replace(".", ",") if num in ("fr", "de") else s) + " %"


# ---------------------------------------------------------------- purchase documents

def render_invoice(path: Path, inv, entities, w, cust_no="AZM-0041", seed=0):
    s = inv.s
    lang = s.lang
    T = LBL[lang]
    n = lambda x: fmt(x, s.num)  # noqa: E731
    dd = lambda x: fdate(x, s.dstyle)  # noqa: E731
    cust = entities[inv.customer]
    is_cn = inv.kind == "credit_note"
    title = T["credit_note"] if is_cn else T["invoice"]
    po = w.pos.get(inv.po) if inv.po else None

    def page_label(c, p, total):
        c.setFont("Sans", 7)
        c.setFillColor(GREY)
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {p} / {total}" if lang == "fr" else f"Page {p} of {total}")

    doc = Doc(path, f"{title} {inv.number}", s.name, page_label=page_label, creator=f"{s.name} invoicing")
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    meta = [(T["cn_no"] if is_cn else T["no"], inv.number), (T["cn_date"] if is_cn else T["date"], dd(inv.date))]
    if "due_date" not in inv.omit and not is_cn:
        meta.append((T["due"], dd(inv.due)))
    meta.append((T["cust"], cust_no if inv.customer == "AMS" else "AZC-0007"))
    if po:
        meta.append((T["po"], po.number))
    if inv.dn:
        meta.append((T["dn"], inv.dn))
    if is_cn:
        meta.append((T["orig"], inv.ref_invoice))
    if inv.vessel and inv.vessel != "FLEET":
        from world import VESSELS
        meta.append((T["vessel"], VESSELS[inv.vessel].split(" (")[0]))
    if inv.period:
        meta.append((T["period"], inv.period))

    sup_lines = [s.name, s.street, f"{s.city}, {s.country}"]
    if "supplier_address" in inv.omit:
        sup_lines = [s.name]
    contact = [f"Tel. {s.phone}", s.email]
    if "supplier_vat" not in inv.omit and s.vat_id:
        contact.append(("N° TVA " if lang == "fr" else "VAT ID ") + s.vat_id)
    bill = [cust["name"], cust["street"], cust["city"], cust["country"], ("N° TVA " if lang == "fr" else "VAT ID ") + cust["vat"]]

    style = s.style
    if style == "modern":
        band = HexColor(s.color)
        doc.rect(0, H - 32 * mm, W, 32 * mm, fill=band)
        doc.logo(left, H - 25 * mm, s.logo, "#FFFFFF", "", size=18 * mm)
        doc.logo(left + 1.5 * mm, H - 23.5 * mm, s.logo, s.color, initials(s.name), size=15 * mm)
        doc.text(left + 22 * mm, H - 14 * mm, s.name, "Sans-B", 15, white)
        doc.text(left + 22 * mm, H - 20 * mm, s.activity, "Sans", 8.5, white)
        doc.text(right, H - 17 * mm, title, "Sans-B", 22, white, "r")
        y = H - 42 * mm
        for k, t in enumerate(sup_lines + contact):
            doc.text(left, y - k * 10.5, t, "Sans-B" if k == 0 else "Sans", 8.2, black if k == 0 else GREY)
        doc.kv(right - 72 * mm, y, meta, label_w=30 * mm, size=8.4)
        y = H - 42 * mm - max(len(sup_lines + contact), len(meta)) * 11 - 10
        doc.rect(left, y - 52, 82 * mm, 58, fill=LIGHT, r=3)
        doc.text(left + 6, y - 6, T["bill"].upper(), "Sans-B", 7.5, band)
        for k, t in enumerate(bill):
            doc.text(left + 6, y - 19 - k * 9.5, t, "Sans-B" if k == 0 else "Sans", 8.2)
        y -= 72
        head_fill = band
        f, fb = "Sans", "Sans-B"
    elif style == "classic":
        doc.logo(W / 2 - 9 * mm, H - 30 * mm, s.logo, s.color, initials(s.name), size=18 * mm)
        doc.text(W / 2, H - 37 * mm, s.name.upper(), "Serif-B", 15, HexColor(s.color), "c")
        doc.text(W / 2, H - 42.5 * mm, " · ".join(sup_lines[1:] + contact[:2]) if len(sup_lines) > 1 else s.email,
                 "Serif", 8, GREY, "c", maxw=W - 40 * mm)
        doc.hline(left, right, H - 46 * mm, HexColor(s.color), 1.2)
        doc.hline(left, right, H - 47.2 * mm, HexColor(s.color), 0.4)
        doc.text(left, H - 58 * mm, title, "Serif-B", 20, black)
        y = H - 68 * mm
        doc.text(left, y, T["bill"], "Serif-I", 9, GREY)
        for k, t in enumerate(bill):
            doc.text(left, y - 12 - k * 10.5, t, "Serif-B" if k == 0 else "Serif", 9)
        doc.kv(right - 75 * mm, H - 58 * mm, meta, f="Serif", fb="Serif-B", label_w=32 * mm, size=9, gap=12)
        if len(contact) > 2:
            doc.text(left, y - 12 - len(bill) * 10.5 - 4, contact[2], "Serif", 8, GREY)
        y = y - 12 - len(bill) * 10.5 - 24
        head_fill = HexColor(s.color)
        f, fb = "Serif", "Serif-B"
    elif style in ("din", "fr"):
        accent = HexColor(s.color)
        doc.logo(right - 20 * mm, H - 30 * mm, s.logo, s.color, initials(s.name), size=20 * mm)
        doc.text(left, H - 20 * mm, s.name, "Sans-B" if style == "din" else "DV-B", 16, accent)
        doc.text(left, H - 26 * mm, s.activity, "Sans", 8.5, GREY)
        doc.text(left, H - 45 * mm, f"{s.name} · {s.street} · {s.city}"[:110], "Sans", 6.5, GREY)
        doc.hline(left, left + 85 * mm, H - 46.5 * mm, GREY, 0.3)
        for k, t in enumerate(bill):
            doc.text(left, H - 52 * mm - k * 10.5, t, "Sans-B" if k == 0 else "Sans", 9)
        doc.rect(right - 78 * mm, H - 50 * mm - len(meta) * 11.5 - 4, 78 * mm, len(meta) * 11.5 + 18, fill=LIGHT, r=2)
        doc.text(right - 75 * mm, H - 44 * mm, title, "Sans-B", 13, accent)
        doc.kv(right - 75 * mm, H - 52 * mm, meta, label_w=31 * mm, size=8.4)
        y = H - 52 * mm - max(len(bill) * 10.5, len(meta) * 11.5) - 22
        if style == "din":
            doc.text(left, y, f"{title.title()} {inv.number}", "Sans-B", 11)
            y -= 16
            doc.text(left, y, "Dear Sir or Madam, we hereby invoice the following goods and services:", "Sans", 9)
            y -= 16
        head_fill = accent
        f, fb = "Sans", "Sans-B"
    else:  # plain (non-compliant one-man business invoice)
        doc.text(left, H - 25 * mm, s.name.upper(), "Sans-B", 18)
        doc.text(left, H - 31 * mm, f"Tel. {s.phone}  ·  {s.email}", "Sans", 9, GREY)
        doc.text(left, H - 48 * mm, f"INVOICE No {inv.number.split()[-1]}", "Sans-B", 14)
        doc.text(left, H - 56 * mm, f"Date: {dd(inv.date)}", "Sans", 10)
        doc.text(left, H - 68 * mm, f"To: {cust['name']}", "Sans", 10)
        doc.text(left, H - 75 * mm, f"Vessel: M/Y Selene", "Sans", 10)
        y = H - 90 * mm
        doc.hline(left, right, y + 4, black, 0.8)
        doc.text(left, y - 8, "Description", "Sans-B", 10)
        doc.text(right, y - 8, "EUR", "Sans-B", 10, align="r")
        doc.hline(left, right, y - 13, black, 0.4)
        doc.text(left, y - 28, inv.lines[0].desc, "Sans", 10, maxw=140 * mm)
        doc.text(right, y - 28, n(inv.total), "Sans", 10, align="r")
        doc.hline(left, right, y - 40, black, 0.4)
        doc.text(right - 35 * mm, y - 56, "TOTAL", "Sans-B", 12, align="r")
        doc.text(right, y - 56, f"{n(inv.total)} EUR", "Sans-B", 12, align="r")
        doc.text(left, y - 90, "Payment by bank transfer:", "Sans", 9)
        doc.text(left, y - 102, f"IBAN {s.iban}  ·  BIC {s.bic}", "Sans", 9)
        doc.text(left, y - 130, "Thank you for your business!", "Sans-I", 9, GREY)
        doc.save()
        return

    # line items
    show_vat_col = s.regime in ("VAT20", "MIXED")
    cols = [("#", 7 * mm, "c"), (T["item"], 22 * mm, "l"), (T["desc"], 70 * mm if show_vat_col else 83 * mm, "l"),
            (T["qty"], 13 * mm, "r"), (T["unit"], 12 * mm, "c"), (T["price"], 20 * mm, "r")]
    if show_vat_col:
        cols.append((T["vat"], 13 * mm, "r"))
    cols.append((T["amount"], 22 * mm if not show_vat_col else 22 * mm, "r"))
    rows = []
    for k, ln in enumerate(inv.lines, 1):
        q = f"{ln.qty.normalize():f}"
        if s.num in ("fr", "de"):
            q = q.replace(".", ",")
        price = fmt(ln.price, s.num) if ln.price.as_tuple().exponent >= -2 else (
            f"{ln.price:.3f}".replace(".", "," if s.num in ("fr", "de") else "."))
        row = [str(k), ln.sku or "—", ln.desc, q, ln.unit, price]
        if show_vat_col:
            row.append(pct(ln.rate, s.num))
        row.append(n(ln.amount))
        rows.append(row)
    y = doc.table(left, y, cols, rows, head_fill=head_fill, f=f, fb=fb, size=7.8, row_h=14)

    # totals
    y -= 8
    tx = right - 70 * mm
    totals = [(T["net"], n(inv.net))]
    if s.regime in ("VAT20", "MIXED"):
        if "vat_breakdown" not in inv.omit:
            for rate, (base, vat) in sorted(inv.vat_by_rate().items()):
                totals.append((f"{T['vat']} {pct(rate, s.num)}", n(inv.vat if len(inv.vat_by_rate()) == 1 else vat)))
    else:
        totals.append((T["vat"], n(D(0))))
    totals.append((T["total"], n(inv.total)))
    if inv.deposit:
        totals.append((T["deposit"] + f" ({fdate(dt.date(2026, 9, 2), s.dstyle)})", "-" + n(inv.deposit)))
        totals.append((T["topay"], n(inv.payable)))
    for k, (a, b) in enumerate(totals):
        last = k == len(totals) - 1
        if last:
            doc.rect(tx - 4, y - 5, right - tx + 4, 15, fill=head_fill)
        doc.text(tx, y, a, fb if last else f, 8.6, white if last else black)
        doc.text(right - 3, y, b, fb, 8.6, white if last else black, "r")
        y -= 15 if last else 13
    y -= 6

    # VAT summary / legal VAT mention
    if s.regime == "MIXED":
        doc.text(left, y, T["vat_summary"], fb, 8)
        y -= 4
        vrows = [[pct(r, s.num), n(b), n(v)] for r, (b, v) in sorted(inv.vat_by_rate().items())]
        y = doc.table(left, y, [(T["rate"], 18 * mm, "l"), (T["base"], 26 * mm, "r"), (T["vat"], 22 * mm, "r")], vrows,
                      head_fill=LIGHT, head_color=black, size=7.5, row_h=12, zebra=None)
    elif s.regime == "RC":
        y = doc.para(left, y, T["rc"], right - left, f, 8, color=GREY)
    elif s.regime == "EXEMPT":
        y = doc.para(left, y, T["exempt"], right - left, f, 8, color=GREY)
    for note in inv.notes:
        y = doc.para(left, y - 2, note, right - left, f, 8, color=GREY)
    y -= 6

    # payment block
    if not is_cn:
        doc.rect(left, y - 46, right - left, 50, stroke=RULE, lw=0.6, r=3)
        doc.text(left + 6, y - 8, T["pay"], fb, 8.5, head_fill)
        terms = T["days"].format(n=s.terms) if "due_date" not in inv.omit else ""
        doc.kv(left + 6, y - 21, [("IBAN", s.iban), ("BIC", s.bic)], label_w=12 * mm, size=8)
        doc.kv(left + 85 * mm, y - 21, [(T["ref"], inv.number), (T["terms"], terms)], label_w=34 * mm, size=8)
        doc.text(left + 6, y - 43, s.bank, f, 7.5, GREY)
        y -= 58
    else:
        y = doc.para(left, y, "This credit note will be offset against the original invoice." if lang == "en" else
                     "Cet avoir vient en déduction de la facture d'origine.", right - left, f, 8, color=GREY) - 6
    if lang == "fr":
        y = doc.para(left, y, FR_LEGAL, right - left, f, 7, color=GREY)

    # footer
    doc.hline(left, right, 17 * mm, RULE)
    foot = [s.name, s.reg, (("TVA intracommunautaire " if lang == "fr" else "VAT ID ") + s.vat_id) if s.vat_id else ""]
    doc.text(left, 13.5 * mm, " · ".join(x for x in foot if x), "Sans", 6.8, GREY, maxw=right - left - 25 * mm)

    if inv.copy_mark:
        doc.c.saveState()
        doc.c.setFillColor(HexColor("#D5D5D5"))
        doc.c.setFont("Sans-B", 54)
        doc.c.translate(W / 2, H / 2)
        doc.c.rotate(35)
        doc.c.drawCentredString(0, 0, inv.copy_mark)
        doc.c.restoreState()
    if inv.stamp:
        doc.stamp(right - 62 * mm, 40 * mm, ["AZUR MARINE SERVICES", inv.stamp, "ACCOUNTS PAYABLE"], color=RED)
    doc.save()


def render_po(path: Path, po, sup, entities, w):
    from world import PEOPLE, VESSELS
    e = entities["AMS"]

    def page_label(c, p, total):
        c.setFont("Sans", 7)
        c.setFillColor(GREY)
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{po.number} · Page {p} of {total}")

    doc = Doc(path, f"Purchase order {po.number}", e["name"], page_label=page_label)
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    doc.rect(0, H - 6 * mm, W, 6 * mm, fill=NAVY)
    doc.rect(0, H - 7.5 * mm, W, 1.5 * mm, fill=TEAL)
    doc.logo(left, H - 30 * mm, "wave", "#0D2C54", "AMS", size=17 * mm)
    doc.text(left + 21 * mm, H - 18 * mm, e["name"], "Sans-B", 14, NAVY)
    doc.text(left + 21 * mm, H - 23.5 * mm, f"{e['street']} · {e['city']} · {e['country']}", "Sans", 8, GREY)
    doc.text(left + 21 * mm, H - 28 * mm, f"VAT ID {e['vat']} · {e['reg']} · {e['nis']}", "Sans", 8, GREY)
    doc.text(right, H - 18 * mm, "PURCHASE ORDER", "Sans-B", 17, NAVY, "r")
    doc.text(right, H - 24 * mm, po.number, "Sans-B", 12, TEAL, "r")
    y = H - 42 * mm
    doc.rect(left, y - 62, 84 * mm, 70, fill=LIGHT, r=3)
    doc.text(left + 6, y - 4, "SUPPLIER", "Sans-B", 7.5, NAVY)
    for k, t in enumerate([sup.name, sup.street, f"{sup.city}, {sup.country}", f"VAT ID {sup.vat_id}" if sup.vat_id else "",
                           sup.email]):
        doc.text(left + 6, y - 16 - k * 9.5, t, "Sans-B" if k == 0 else "Sans", 8.2)
    vessel = VESSELS.get(po.vessel, "Fleet (all managed vessels)")
    meta = [("PO date", fdate(po.date)), ("Supplier code", sup.account), ("Requested by", PEOPLE[po.requested_by][0]),
            ("Vessel", vessel), ("Delivery to", "Quai Antoine Ier, 98000 Monaco"), ("Currency", "EUR")]
    doc.kv(right - 80 * mm, y - 4, meta, label_w=28 * mm, size=8.4)
    y -= 80
    cols = [("#", 8 * mm, "c"), ("Supplier ref.", 24 * mm, "l"), ("Description", 78 * mm, "l"), ("Qty", 14 * mm, "r"),
            ("Unit", 12 * mm, "c"), ("Unit price", 18 * mm, "r"), ("Net amount", 20 * mm, "r")]
    rows = [[str(k), ln.sku or "—", ln.desc, f"{ln.qty.normalize():f}", ln.unit,
             f"{ln.price:,.3f}" if ln.price.as_tuple().exponent < -2 else fmt(ln.price), fmt(ln.amount)]
            for k, ln in enumerate(po.lines, 1)]
    y = doc.table(left, y, cols, rows, head_fill=NAVY, size=7.8, row_h=14)
    y -= 8
    doc.rect(right - 86 * mm, y - 6, 86 * mm, 16, fill=NAVY)
    doc.text(right - 83 * mm, y, "TOTAL NET AMOUNT (EUR, excl. VAT)", "Sans-B", 8.5, white)
    doc.text(right - 3, y, fmt(po.net), "Sans-B", 8.5, white, "r")
    y -= 26
    terms = po.terms or f"{sup.terms} days net from invoice date"
    for k, (a, b) in enumerate([("Payment terms", terms), ("Invoicing", "Invoices must quote this PO number and be sent to "
                                                                         "accounts.payable@azurmarine.example")]):
        doc.text(left, y, a, "Sans-B", 8.2)
        y = doc.para(left + 32 * mm, y, b, right - left - 32 * mm, "Sans", 8.2)
    for note in po.notes:
        y = doc.para(left + 32 * mm, y, note, right - left - 32 * mm, "Sans", 8.2, color=GREY)
    y -= 12
    # approval block
    name, role = PEOPLE[po.approver]
    doc.rect(left, y - 66, right - left, 72, stroke=RULE, lw=0.6, r=3)
    doc.text(left + 6, y - 6, "APPROVAL", "Sans-B", 8, NAVY)
    doc.kv(left + 6, y - 20, [("Approved by", name), ("Function", role), ("Date", fdate(po.date))], label_w=25 * mm,
           size=8.4)
    doc.text(left + 105 * mm, y - 20, "Signature", "Sans", 8, GREY)
    doc.signature(left + 105 * mm, y - 52, seed=po.number + po.approver)
    y -= 84
    doc.para(left, y, "This purchase order is governed by the General Purchasing Conditions of Azur Marine Services "
             "S.A.M. (version 2025-01), available on request. Partial deliveries must be notified in writing. The "
             "supplier shall invoice only the quantities actually delivered.", right - left, "Sans", 7, color=GREY)
    doc.hline(left, right, 17 * mm, RULE)
    doc.text(left, 13.5 * mm, f"{e['name']} · {e['capital']} · {e['reg']} · {e['phone']}", "Sans", 6.8, GREY)
    doc.save()


def render_dn(path: Path, dn, sup, entities, w):
    from world import VESSELS
    e = entities["AMS"]
    lang = sup.lang
    service = dn.kind == "service"
    if lang == "fr":
        title = "FICHE D'INTERVENTION" if service else "BON DE LIVRAISON"
        heads = ("Désignation", "Qté commandée", "Qté livrée", "U") if not service else ("Travaux réalisés", "Prévu", "Réalisé", "U")
        lab = dict(no="N°", date="Date", po="Commande client", vessel="Navire", sign="Réception / visa client",
                   remarks="Observations")
    else:
        title = "SERVICE REPORT" if service else "DELIVERY NOTE"
        heads = ("Description", "Ordered", "Delivered", "Unit") if not service else ("Work performed", "Planned", "Done", "Unit")
        lab = dict(no="No.", date="Date", po="Customer PO", vessel="Vessel", sign="Received by (name, signature)",
                   remarks="Remarks")
    doc = Doc(path, f"{title.title()} {dn.number}", sup.name)
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    doc.logo(left, H - 32 * mm, sup.logo, sup.color, initials(sup.name), size=18 * mm)
    doc.text(left + 22 * mm, H - 20 * mm, sup.name, "Sans-B", 14, HexColor(sup.color) if sup.color != "#000000" else black)
    if sup.street:
        doc.text(left + 22 * mm, H - 26 * mm, f"{sup.street} · {sup.city}", "Sans", 8, GREY)
    doc.text(left + 22 * mm, H - 30.5 * mm, f"Tel. {sup.phone} · {sup.email}", "Sans", 8, GREY)
    doc.text(right, H - 20 * mm, title, "Sans-B", 15, black, "r")
    po = w.pos.get(dn.po) if dn.po else None
    meta = [(lab["no"], dn.number), (lab["date"], fdate(dn.date, sup.dstyle))]
    if po:
        meta.append((lab["po"], po.number))
    meta.append((lab["vessel"], VESSELS[dn.vessel].split(" (")[0]))
    doc.kv(right - 70 * mm, H - 40 * mm, meta, label_w=30 * mm, size=9)
    y = H - 40 * mm
    for k, t in enumerate([e["name"], "Delivery: Quai Antoine Ier", e["city"]]):
        doc.text(left, y - k * 11, t, "Sans-B" if k == 0 else "Sans", 9)
    y -= 70
    cols = [(heads[0], 110 * mm, "l"), (heads[1], 22 * mm, "r"), (heads[2], 22 * mm, "r"), (heads[3], 20 * mm, "c")]

    def q(v):
        s = f"{v.normalize():f}"
        return s.replace(".", ",") if sup.num in ("fr", "de") else s
    rows = [[d, q(o), q(dl), u] for d, o, dl, u in dn.items]
    y = doc.table(left, y, cols, rows, head_fill=HexColor(sup.color) if sup.color != "#000000" else GREY, size=8.2,
                  row_h=15)
    y -= 16
    if dn.remarks:
        doc.text(left, y, f"{lab['remarks']}: {dn.remarks}", "Sans-B", 9, RED)
        y -= 18
    doc.rect(left, y - 70, right - left, 70, stroke=RULE, lw=0.6)
    doc.text(left + 6, y - 12, lab["sign"], "Sans", 8, GREY)
    doc.text(left + 6, y - 28, dn.signed_by, "Sans-B", 9)
    doc.text(left + 6, y - 40, fdate(dn.date), "Sans", 9)
    doc.signature(left + 95 * mm, y - 50, seed=dn.number)
    doc.hline(left, right, 17 * mm, RULE)
    doc.text(left, 13.5 * mm, f"{sup.name} · {sup.reg}" if sup.reg else sup.name, "Sans", 6.8, GREY)
    doc.save()


def render_quote(path: Path, kind: str, number: str, d: dt.date, sup, lines, entities, valid_days=30, note=""):
    """Supplier quote or pro-forma (no accounting entry)."""
    e = entities["AMS"]
    title = {"quote": "QUOTATION", "proforma": "PRO-FORMA INVOICE"}[kind]
    doc = Doc(path, f"{title.title()} {number}", sup.name)
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    accent = HexColor(sup.color)
    doc.logo(left, H - 30 * mm, sup.logo, sup.color, initials(sup.name), size=18 * mm)
    doc.text(left + 22 * mm, H - 18 * mm, sup.name, "Sans-B", 14, accent)
    doc.text(left + 22 * mm, H - 24 * mm, f"{sup.street} · {sup.city} · {sup.country}", "Sans", 8, GREY)
    doc.text(left + 22 * mm, H - 28.5 * mm, f"VAT ID {sup.vat_id} · {sup.reg}", "Sans", 8, GREY)
    doc.text(right, H - 18 * mm, title, "Sans-B", 15, black, "r")
    meta = [("Number", number), ("Date", fdate(d, sup.dstyle)), ("Valid until", fdate(d + dt.timedelta(days=valid_days), sup.dstyle)),
            ("Customer", e["name"])]
    doc.kv(right - 80 * mm, H - 40 * mm, meta, label_w=26 * mm, size=8.6)
    y = H - 40 * mm
    for k, t in enumerate([e["name"], e["street"], e["city"]]):
        doc.text(left, y - k * 11, t, "Sans-B" if k == 0 else "Sans", 9)
    y -= 60
    rows = [[str(k), ln.sku, ln.desc, f"{ln.qty.normalize():f}", fmt(ln.price, sup.num), fmt(ln.amount, sup.num)]
            for k, ln in enumerate(lines, 1)]
    y = doc.table(left, y, [("#", 8 * mm, "c"), ("Item", 22 * mm, "l"), ("Description", 86 * mm, "l"), ("Qty", 14 * mm, "r"),
                            ("Unit price", 20 * mm, "r"), ("Amount", 24 * mm, "r")], rows, head_fill=accent, size=7.8,
                  row_h=14)
    tot = sum((ln.amount for ln in lines), D(0))
    y -= 10
    doc.text(right - 60 * mm, y, "Total (EUR, excl. VAT)", "Sans-B", 9)
    doc.text(right - 3, y, fmt(tot, sup.num), "Sans-B", 9, align="r")
    y -= 24
    txt = ("This document is not an invoice and does not create a payment obligation. Prices are quoted DAP Monaco. "
           if kind == "quote" else "PRO-FORMA – NOT A TAX INVOICE. Issued for approval and customs purposes only; the "
           "commercial invoice will be issued upon shipment. ")
    y = doc.para(left, y, txt + note, right - left, "Sans", 8.5, color=GREY)
    doc.hline(left, right, 17 * mm, RULE)
    doc.text(left, 13.5 * mm, f"{sup.name} · {sup.reg} · VAT ID {sup.vat_id}", "Sans", 6.8, GREY)
    doc.save()


def render_supplier_statement(path: Path, sup, entities, rows, d: dt.date, balance, note=""):
    """rows = [(date, ref, description, debit, credit)] from the supplier's books (customer account)."""
    e = entities["AMS"]
    doc = Doc(path, f"Statement of account {sup.name} {fdate(d)}", sup.name)
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    accent = HexColor(sup.color)
    doc.logo(left, H - 30 * mm, sup.logo, sup.color, initials(sup.name), size=18 * mm)
    doc.text(left + 22 * mm, H - 18 * mm, sup.name, "Sans-B", 14, accent)
    doc.text(left + 22 * mm, H - 24 * mm, f"{sup.street} · {sup.city} · {sup.country}", "Sans", 8, GREY)
    fr = sup.lang == "fr"
    doc.text(right, H - 18 * mm, "RELEVÉ DE COMPTE CLIENT" if fr else "STATEMENT OF ACCOUNT", "Sans-B", 14, black, "r")
    doc.kv(right - 80 * mm, H - 40 * mm, [("Customer" if not fr else "Client", e["name"]), ("Account" if not fr else "Compte", "AZM-0041"),
                                         ("Statement date" if not fr else "Date du relevé", fdate(d, sup.dstyle))],
           label_w=28 * mm, size=8.6)
    y = H - 70 * mm
    rr = [[fdate(a, sup.dstyle), b, c, fmt(dd, sup.num) if dd else "", fmt(cc, sup.num) if cc else ""] for a, b, c, dd, cc in rows]
    y = doc.table(left, y, [("Date", 22 * mm, "l"), ("Reference", 34 * mm, "l"), ("Description", 70 * mm, "l"),
                            ("Debit", 24 * mm, "r"), ("Credit", 24 * mm, "r")], rr, head_fill=accent, size=8, row_h=14)
    y -= 12
    doc.rect(right - 80 * mm, y - 6, 80 * mm, 17, fill=accent)
    doc.text(right - 77 * mm, y, ("Solde dû au " if fr else "Balance due at ") + fdate(d, sup.dstyle), "Sans-B", 9, white)
    doc.text(right - 3, y, f"EUR {fmt(balance, sup.num)}", "Sans-B", 9, white, "r")
    y -= 30
    if note:
        doc.para(left, y, note, right - left, "Sans", 8.5, color=GREY)
    doc.hline(left, right, 17 * mm, RULE)
    doc.text(left, 13.5 * mm, f"{sup.name} · {sup.reg} · IBAN {sup.iban} · BIC {sup.bic}", "Sans", 6.8, GREY)
    doc.save()


# ---------------------------------------------------------------- bank

def render_bank_statement(path: Path, lines, opening, d1, d2, number, bank, holder):
    def page_label(c, p, total):
        c.setFont("Sans", 7)
        c.setFillColor(GREY)
        c.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Relevé n° {number} – page {p}/{total}")

    doc = Doc(path, f"Relevé de compte {number}", bank["name"], page_label=page_label, creator="BRM e-Statement")
    W, H = doc.W, doc.H
    left, right = 15 * mm, W - 15 * mm
    burgundy = HexColor("#7A1F2B")

    def header():
        doc.rect(left, H - 24 * mm, 14 * mm, 14 * mm, fill=burgundy)
        doc.text(left + 7 * mm, H - 19.5 * mm, "BRM", "Serif-B", 11, white, "c")
        doc.text(left + 17 * mm, H - 15 * mm, bank["name"].upper(), "Serif-B", 13, burgundy)
        doc.text(left + 17 * mm, H - 20 * mm, f"{bank['branch']} · {bank['street']} · {bank['city']}", "Sans", 7.5, GREY)
        doc.text(right, H - 15 * mm, "RELEVÉ DE COMPTE", "Sans-B", 12, black, "r")
        doc.text(right, H - 20 * mm, f"du {fdate(d1)} au {fdate(d2)}", "Sans", 8.5, black, "r")
        y = H - 32 * mm
        doc.rect(left, y - 30, right - left, 34, fill=LIGHT, r=2)
        doc.kv(left + 5, y - 6, [("Titulaire", holder["name"]), ("Adresse", f"{holder['street']}, {holder['city']}")],
               label_w=22 * mm, size=8)
        doc.kv(left + 105 * mm, y - 6, [("IBAN", bank["account_iban"]), ("BIC", bank["bic"])], label_w=12 * mm, size=8)
        doc.text(left + 5, y - 28, f"Compte courant professionnel EUR n° {bank['account_no']} · Relevé n° {number}", "Sans",
                 7.5, GREY)
        return y - 42

    cols = [("Date", 18 * mm, "l"), ("Libellé de l'opération", 98 * mm, "l"), ("Valeur", 18 * mm, "l"),
            ("Débit", 23 * mm, "r"), ("Crédit", 23 * mm, "r")]
    balance = opening
    tot_d, tot_c = D(0), D(0)
    rows = [[fdate(d1), "SOLDE CRÉDITEUR AU " + fdate(d1 - dt.timedelta(days=1)), "", "", fmt(opening, "fr")]]
    for b in lines:
        rows.append([fdate(b.date), b.label, fdate(b.vdate), fmt(b.debit, "fr") if b.debit else "",
                     fmt(b.credit, "fr") if b.credit else ""])
        balance += b.credit - b.debit
        tot_d += b.debit
        tot_c += b.credit

    state = {"page": 0}

    def brk():
        doc.text(right, 22 * mm, "à reporter", "Sans-I", 7.5, GREY, "r")
        doc.new_page()
        state["page"] += 1
        return header()

    y = header()
    y = doc.table(left, y, cols, rows, head_fill=burgundy, size=7.6, row_h=12.2, bottom=30 * mm, on_break=brk,
                  bold_rows=(0,))
    y -= 6
    if y < 45 * mm:
        y = brk()
    doc.hline(left, right, y + 2, black, 0.6)
    doc.text(left + 18 * mm + 3, y - 8, "TOTAL DES MOUVEMENTS", "Sans-B", 8)
    doc.text(right - 23 * mm - 3, y - 8, fmt(tot_d, "fr"), "Sans-B", 8, align="r")
    doc.text(right - 3, y - 8, fmt(tot_c, "fr"), "Sans-B", 8, align="r")
    doc.rect(left, y - 30, right - left, 15, fill=burgundy)
    doc.text(left + 18 * mm + 3, y - 25, f"NOUVEAU SOLDE CRÉDITEUR AU {fdate(d2)}", "Sans-B", 8.5, white)
    doc.text(right - 3, y - 25, fmt(balance, "fr"), "Sans-B", 8.5, white, "r")
    doc.para(left, y - 46, "Les opérations sont présentées par date d'opération. La date de valeur détermine le calcul des "
             "intérêts. Toute réclamation doit être formulée dans un délai de 30 jours à compter de la réception du "
             "présent relevé. Garantie des dépôts : voir le formulaire d'information des déposants.", right - left,
             "Sans", 6.8, color=GREY)
    doc.save()
    return balance


def render_payment_batch(path: Path, batch_id, d, payments, bank, holder):
    doc = Doc(path, f"Ordre de virements {batch_id}", bank["name"], creator="BRM Online Business")
    W, H = doc.W, doc.H
    left, right = 15 * mm, W - 15 * mm
    burgundy = HexColor("#7A1F2B")
    doc.rect(0, H - 14 * mm, W, 14 * mm, fill=burgundy)
    doc.text(left, H - 9 * mm, "BRM Online Business", "Sans-B", 12, white)
    doc.text(right, H - 9 * mm, "Avis d'exécution – virements SEPA", "Sans", 10, white, "r")
    y = H - 26 * mm
    doc.kv(left, y, [("Donneur d'ordre", holder["name"]), ("Compte débité", bank["account_iban"]),
                     ("Référence lot", batch_id), ("Date d'exécution", fdate(d)),
                     ("Statut", "EXÉCUTÉ"), ("Saisi par / validé par", "S. BIANCHI / C. MARTIN")], label_w=40 * mm, size=8.5)
    y -= 80
    rows = []
    for k, p in enumerate(payments, 1):
        rows.append([str(k), p.payee_name, p.iban, p.bic, p.ref, fmt(p.amount, "fr")])
    y = doc.table(left, y, [("#", 7 * mm, "c"), ("Bénéficiaire", 50 * mm, "l"), ("IBAN bénéficiaire", 55 * mm, "l"),
                            ("BIC", 24 * mm, "l"), ("Référence", 21 * mm, "l"), ("Montant EUR", 23 * mm, "r")], rows,
                  head_fill=burgundy, size=7.4, row_h=13)
    tot = sum((p.amount for p in payments), D(0))
    y -= 8
    doc.text(right - 50 * mm, y, f"Total du lot ({len(payments)} virement{'s' if len(payments) > 1 else ''})", "Sans-B", 8.5)
    doc.text(right - 3, y, fmt(tot, "fr"), "Sans-B", 8.5, align="r")
    y -= 24
    doc.para(left, y, "Les coordonnées bancaires des bénéficiaires sont celles saisies dans l'ordre. La banque n'effectue "
             "aucun contrôle de concordance entre le nom du bénéficiaire et l'IBAN pour les virements hors zone de "
             "vérification. Document généré automatiquement – ne pas répondre.", right - left, "Sans", 7, color=GREY)
    doc.save()


# ---------------------------------------------------------------- accounting exports (landscape)

def _report_doc(path, title, subtitle, entity, edited: dt.datetime, creator="Comptaflux ERP 9.2"):
    def page_label(c, p, total):
        c.setFont("Mono", 7)
        c.setFillColor(GREY)
        c.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Page {p}/{total}")

    doc = Doc(path, title, entity["name"], land=True, page_label=page_label, creator=creator)
    W, H = doc.W, doc.H
    left, right = 12 * mm, W - 12 * mm

    def header():
        doc.text(left, H - 12 * mm, entity["name"], "Sans-B", 10)
        doc.text(left, H - 16.5 * mm, f"Dossier AZM · Exercice 01/01/2026 – 31/12/2026 · {creator}", "Sans", 7, GREY)
        doc.text(W / 2, H - 12 * mm, title, "Sans-B", 12, NAVY, "c")
        doc.text(W / 2, H - 17 * mm, subtitle, "Sans", 8, GREY, "c")
        doc.text(right, H - 12 * mm, f"Édité le {edited:%d/%m/%Y à %H:%M}", "Sans", 7.5, GREY, "r")
        doc.text(right, H - 16.5 * mm, "par imorel", "Sans", 7.5, GREY, "r")
        doc.hline(left, right, H - 19.5 * mm, NAVY, 0.8)
        return H - 25 * mm

    return doc, left, right, header


def render_journal(path, entries, month_label, entity, edited):
    doc, left, right, header = _report_doc(path, "JOURNAL DES ACHATS (AC)", f"Période : {month_label} · tri par date de "
                                           "saisie", entity, edited)
    cols = [("Pièce", 22 * mm, "l"), ("Date", 18 * mm, "l"), ("Compte", 18 * mm, "l"), ("Fournisseur", 52 * mm, "l"),
            ("N° facture", 30 * mm, "l"), ("Libellé", 54 * mm, "l"), ("Charge", 15 * mm, "l"), ("HT", 22 * mm, "r"),
            ("TVA", 19 * mm, "r"), ("TTC", 23 * mm, "r")]
    rows, th, tv, tt = [], D(0), D(0), D(0)
    for piece, d, i in entries:
        sgn = i.sign
        net, vat, tot = i.net * sgn, i.vat * sgn, i.total * sgn
        if i.s.regime in ("RC",):
            vat_s = "autoliq."
        else:
            vat_s = fmt(vat, "fr")
        label = ("Avoir " if i.kind == "credit_note" else "Fact. ") + i.lines[0].desc
        rows.append([piece, fdate(d), i.s.account, i.s.name, i.number, label, i.s.expense, fmt(net, "fr"), vat_s,
                     fmt(tot, "fr")])
        th, tv, tt = th + net, tv + (vat if i.s.regime != "RC" else 0), tt + tot

    def brk():
        doc.new_page()
        return header()
    y = doc.table(left, header(), cols, rows, head_fill=NAVY, size=7.2, row_h=12.5, bottom=22 * mm, on_break=brk)
    y -= 4
    if y < 30 * mm:
        y = brk()
    doc.hline(left, right, y + 2, black, 0.6)
    doc.text(left + 2, y - 8, f"TOTAL JOURNAL AC – {month_label} ({len(entries)} écritures)", "Sans-B", 8)
    doc.text(right - 42 * mm - 3, y - 8, fmt(th, "fr"), "Sans-B", 8, align="r")
    doc.text(right - 23 * mm - 3, y - 8, fmt(tv, "fr"), "Sans-B", 8, align="r")
    doc.text(right - 3, y - 8, fmt(tt, "fr"), "Sans-B", 8, align="r")
    doc.text(left + 2, y - 22, "autoliq. = TVA autoliquidée (acquisitions intracommunautaires et prestations UE), "
             "comptabilisée en 445200 / 445660 pour un montant net nul.", "Sans", 7, GREY)
    doc.save()


def render_ledger(path, accounts, period_label, entity, edited):
    """accounts = [(account, name, opening, [(date, piece, label, debit, credit)], closing)]"""
    doc, left, right, header = _report_doc(path, "GRAND-LIVRE FOURNISSEURS (401)", period_label, entity, edited)
    cols = [("Date", 20 * mm, "l"), ("Pièce", 24 * mm, "l"), ("Libellé", 120 * mm, "l"), ("Débit", 30 * mm, "r"),
            ("Crédit", 30 * mm, "r"), ("Solde", 36 * mm, "r")]

    def sold(v):
        return f"{fmt(abs(v), 'fr')} {'C' if v > 0 else ('D' if v < 0 else '')}".strip()
    y = header()
    for acc, name, opening, entries, closing in accounts:
        need = 14 * (len(entries) + 3)
        if y - need < 20 * mm:
            doc.new_page()
            y = header()
        doc.rect(left, y - 10, right - left, 13, fill=LIGHT)
        doc.text(left + 2, y - 6, f"{acc}  {name}", "Sans-B", 8.5, NAVY)
        y -= 14
        rows = [["", "", f"Solde au {period_label.split(' au ')[0].replace('Du ', '')}", "", "", sold(opening)]]
        bal = opening
        for d, piece, label, deb, cre in entries:
            bal += cre - deb
            rows.append([fdate(d), piece, label, fmt(deb, "fr") if deb else "", fmt(cre, "fr") if cre else "", sold(bal)])
        rows.append(["", "", f"Total compte {acc}", "", "", sold(closing)])
        y = doc.table(left, y, cols, rows, head=False, size=7.4, row_h=11.5, zebra=None, grid=RULE,
                      bold_rows=(len(rows) - 1,))
        y -= 8
    doc.save()


def render_aged(path, rows, at, entity, edited):
    """rows = [(account, supplier, invoice, inv_date, due, not_due, b1, b2, b3, b4)]"""
    doc, left, right, header = _report_doc(path, "BALANCE ÂGÉE FOURNISSEURS", f"Situation au {fdate(at)} · échéances "
                                           "calculées sur la date d'échéance de la facture", entity, edited)
    cols = [("Compte", 18 * mm, "l"), ("Fournisseur", 52 * mm, "l"), ("N° facture", 30 * mm, "l"), ("Date fact.", 19 * mm, "l"),
            ("Échéance", 19 * mm, "l"), ("Non échu", 23 * mm, "r"), ("1-30 j", 22 * mm, "r"), ("31-60 j", 22 * mm, "r"),
            ("61-90 j", 22 * mm, "r"), ("> 90 j", 22 * mm, "r"), ("Total", 24 * mm, "r")]
    tot = [D(0)] * 6
    out = []
    for acc, name, num, d, due, *b in rows:
        vals = list(b) + [sum(b, D(0))]
        tot = [t + v for t, v in zip(tot, vals)]
        out.append([acc, name, num, fdate(d), fdate(due)] + [fmt(v, "fr") if v else "" for v in vals])
    out.append(["", "TOTAL GÉNÉRAL", "", "", ""] + [fmt(v, "fr") for v in tot])

    def brk():
        doc.new_page()
        return header()
    doc.table(left, header(), cols, out, head_fill=NAVY, size=7.2, row_h=12.5, bottom=20 * mm, on_break=brk,
              bold_rows=(len(out) - 1,))
    doc.save()


def render_master(path, suppliers, entity, edited):
    doc, left, right, header = _report_doc(path, "FICHIER FOURNISSEURS – DONNÉES DE RÉFÉRENCE",
                                           "Extraction des tiers actifs · coordonnées bancaires validées par la "
                                           "direction financière", entity, edited)
    cols = [("Compte", 16 * mm, "l"), ("Raison sociale", 50 * mm, "l"), ("Pays", 17 * mm, "l"), ("N° TVA", 31 * mm, "l"),
            ("IBAN", 58 * mm, "l"), ("BIC", 23 * mm, "l"), ("Téléphone", 27 * mm, "l"), ("Délai", 11 * mm, "r"),
            ("BC requis", 15 * mm, "c"), ("Créé le", 18 * mm, "l")]
    rows = [[s.account, s.name, s.country, s.vat_id or "—", s.iban, s.bic, s.phone, f"{s.terms} j",
             "Oui" if s.po_required else "Non", fdate(s.created)] for s in suppliers]

    def brk():
        doc.new_page()
        return header()
    y = doc.table(left, header(), cols, rows, head_fill=NAVY, size=7.1, row_h=12.5, bottom=25 * mm, on_break=brk)
    doc.para(left, y - 10, "BC requis = « Oui » : toute facture doit être rattachée à un bon de commande approuvé "
             "(procédure achats PRC-FIN-04). « Non » : fournisseurs sous contrat cadre (loyers, télécoms, assurances, "
             "services récurrents, avitaillement alimentaire). Toute modification de coordonnées bancaires doit être "
             "confirmée par contre-appel au numéro de téléphone figurant dans ce fichier.", right - left, "Sans", 7.2,
             color=GREY)
    doc.save()


# ---------------------------------------------------------------- correspondence and long-form documents

def render_email(path, frm, to, d: dt.datetime, subject, body, cc="", attachments=(), sender_name=""):
    doc = Doc(path, subject, frm, creator="Mail export")
    W, H = doc.W, doc.H
    left, right = 20 * mm, W - 20 * mm
    doc.text(left, H - 18 * mm, "Azur Marine Services – messagerie", "Sans", 7.5, GREY)
    doc.text(right, H - 18 * mm, f"Imprimé le {d + dt.timedelta(days=2):%d/%m/%Y}", "Sans", 7.5, GREY, "r")
    doc.hline(left, right, H - 20 * mm, black, 1)
    doc.text(left, H - 30 * mm, subject, "Sans-B", 13, maxw=right - left)
    y = H - 40 * mm
    pairs = [("From:", f"{sender_name} <{frm}>" if sender_name else frm), ("Sent:", d.strftime("%A %d %B %Y %H:%M")),
             ("To:", to)]
    if cc:
        pairs.append(("Cc:", cc))
    pairs.append(("Subject:", subject))
    if attachments:
        pairs.append(("Attachments:", "; ".join(attachments)))
    y = doc.kv(left, y, pairs, label_w=22 * mm, size=8.8, gap=12.5, fb="Sans", color=black)
    doc.hline(left, right, y + 4, RULE)
    y -= 12

    def brk():
        doc.new_page()
        return doc.H - 20 * mm
    y = doc.para(left, y, body, right - left, "Sans", 9.6, leading=13.5, bottom=20 * mm, on_break=brk)
    doc.save()


def render_text_doc(path, title, issuer, sections, d: dt.date, ref="", subtitle="", land=False, color="#0D2C54",
                    footer=""):
    """Generic long-form document: sections = [(heading, paragraphs or ('table', cols, rows))]."""
    accent = HexColor(color)

    def page_label(c, p, total):
        c.setFont("Sans", 7)
        c.setFillColor(GREY)
        c.drawString(20 * mm, 10 * mm, footer or issuer)
        c.drawRightString((landscape(A4) if land else A4)[0] - 20 * mm, 10 * mm, f"{ref + ' · ' if ref else ''}Page {p}/{total}")

    doc = Doc(path, title, issuer, land=land, page_label=page_label)
    W, H = doc.W, doc.H
    left, right = 20 * mm, W - 20 * mm
    doc.rect(left, H - 22 * mm, 4, 12 * mm, fill=accent)
    doc.text(left + 8, H - 15 * mm, issuer, "Sans-B", 9, accent)
    doc.text(left + 8, H - 20.5 * mm, f"{fdate(d)}{' · ' + ref if ref else ''}", "Sans", 8, GREY)
    y = H - 34 * mm
    y = doc.para(left, y, title, right - left, "Sans-B", 16, leading=20)
    if subtitle:
        y = doc.para(left, y, subtitle, right - left, "Sans-I", 10, color=GREY)
    y -= 8

    def brk():
        doc.new_page()
        return doc.H - 20 * mm
    for heading, body in sections:
        if y < 40 * mm:
            y = brk()
        if heading:
            doc.text(left, y, heading, "Sans-B", 10.5, accent)
            y -= 15
        items = body if isinstance(body, list) else [body]
        for item in items:
            if isinstance(item, tuple) and item[0] == "table":
                _, cols, rows = item
                y = doc.table(left, y, cols, rows, head_fill=accent, size=7.8, row_h=13, bottom=25 * mm, on_break=brk) - 8
            else:
                y = doc.para(left, y, item, right - left, "Sans", 9.2, leading=13, bottom=22 * mm, on_break=brk) - 5
        y -= 6
    doc.save()


def render_sales_invoice(path, number, d, client, lines, entity):
    """Invoice issued BY Azur Marine Services (sales side; not part of the purchase cycle)."""
    def page_label(c, p, total):
        c.setFont("Sans", 7)
        c.setFillColor(GREY)
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {p} of {total}")
    doc = Doc(path, f"Invoice {number}", entity["name"], page_label=page_label)
    W, H = doc.W, doc.H
    left, right = 18 * mm, W - 18 * mm
    doc.rect(0, H - 6 * mm, W, 6 * mm, fill=NAVY)
    doc.rect(0, H - 7.5 * mm, W, 1.5 * mm, fill=TEAL)
    doc.logo(left, H - 30 * mm, "wave", "#0D2C54", "AMS", size=17 * mm)
    doc.text(left + 21 * mm, H - 18 * mm, entity["name"], "Sans-B", 14, NAVY)
    doc.text(left + 21 * mm, H - 23.5 * mm, f"{entity['street']} · {entity['city']}", "Sans", 8, GREY)
    doc.text(right, H - 18 * mm, "INVOICE", "Sans-B", 18, NAVY, "r")
    doc.kv(right - 70 * mm, H - 36 * mm, [("Invoice No.", number), ("Date", fdate(d)),
                                         ("Due date", fdate(d + dt.timedelta(days=15)))], label_w=26 * mm, size=8.6)
    y = H - 36 * mm
    for k, t in enumerate(client):
        doc.text(left, y - k * 11, t, "Sans-B" if k == 0 else "Sans", 9)
    y -= 66
    rows = [[str(k), desc, fmt(amt)] for k, (desc, amt) in enumerate(lines, 1)]
    y = doc.table(left, y, [("#", 8 * mm, "c"), ("Description", 136 * mm, "l"), ("Amount EUR", 30 * mm, "r")], rows,
                  head_fill=NAVY, size=8, row_h=14)
    net = sum((a for _, a in lines), D(0))
    vat = (net * D("0.20")).quantize(D("0.01"))
    for k, (a, b) in enumerate([("Net total", net), ("VAT 20 %", vat), ("TOTAL EUR", net + vat)]):
        doc.text(right - 60 * mm, y - 12 - 13 * k, a, "Sans-B" if k == 2 else "Sans", 9)
        doc.text(right - 3, y - 12 - 13 * k, fmt(b), "Sans-B" if k == 2 else "Sans", 9, align="r")
    doc.text(left, y - 70, f"Please pay to IBAN {__import__('world').BANK['account_iban']} · BIC "
             f"{__import__('world').BANK['bic']}", "Sans", 8.5)
    doc.hline(left, right, 17 * mm, RULE)
    doc.text(left, 13.5 * mm, f"{entity['name']} · {entity['capital']} · {entity['reg']} · VAT ID {entity['vat']}",
             "Sans", 6.8, GREY)
    doc.save()
