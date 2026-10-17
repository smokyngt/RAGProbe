"""Small PDF layer for CareBench documents (reportlab platypus, fonts embedded, text layer kept).

Everything a clinical document needs: a header band repeated on every page (hospital + patient banner), tables whose
cells never wrap (font shrinks to fit), prose that flows over several pages, "Page x of y" footer. Output is
deterministic (invariant=1) so the corpus hashes are stable.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

_FONTS = {"Sans": "liberation/LiberationSans-Regular.ttf", "Sans-B": "liberation/LiberationSans-Bold.ttf",
          "Sans-I": "liberation/LiberationSans-Italic.ttf", "Serif": "liberation/LiberationSerif-Regular.ttf",
          "Serif-B": "liberation/LiberationSerif-Bold.ttf", "Mono": "liberation/LiberationMono-Regular.ttf"}
for _n, _f in _FONTS.items():
    pdfmetrics.registerFont(TTFont(_n, f"/usr/share/fonts/truetype/{_f}"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans-I", boldItalic="Sans-B")
registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif", boldItalic="Serif-B")

GREEN = HexColor("#0B6E4F")
SLATE = HexColor("#34495E")
LIGHT = HexColor("#EAF2EF")
RULE = HexColor("#B8C7C1")
RED = HexColor("#A61E1E")

HOSPITAL = "Centre Hospitalier Saint-Aubin"
FOOTER = "Fictional document generated for benchmarking - not medical advice"


class _Canvas(canvas.Canvas):
    def __init__(self, *a, banner=None, doc_ref="", **kw):
        super().__init__(*a, **kw)
        self._st, self._banner, self._ref = [], banner, doc_ref

    def showPage(self):
        self._st.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._st)
        for st in self._st:
            self.__dict__.update(st)
            self._decorate(n)
            super().showPage()
        super().save()

    def _decorate(self, n):
        W, H = self._pagesize
        self.setFillColor(GREEN)
        self.rect(0, H - 14 * mm, W, 14 * mm, stroke=0, fill=1)
        self.setFillColor(white)
        self.setFont("Sans-B", 10)
        self.drawString(15 * mm, H - 9 * mm, HOSPITAL)
        self.setFont("Sans", 8)
        self.drawRightString(W - 15 * mm, H - 9 * mm, self._ref)
        if self._banner:
            self.setFillColor(LIGHT)
            self.rect(0, H - 22 * mm, W, 8 * mm, stroke=0, fill=1)
            self.setFillColor(black)
            self.setFont("Sans-B", 8)
            self.drawString(15 * mm, H - 19.6 * mm, self._banner)
        self.setStrokeColor(RULE)
        self.line(15 * mm, 13 * mm, W - 15 * mm, 13 * mm)
        self.setFillColor(SLATE)
        self.setFont("Sans", 7)
        self.drawString(15 * mm, 9 * mm, FOOTER)
        self.drawRightString(W - 15 * mm, 9 * mm, f"Page {self._pageNumber} of {n}")


def _style(name, size=9.2, font="Sans", lead=None, color=black, after=3, left=0):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=lead or size * 1.35, textColor=color,
                          spaceAfter=after, leftIndent=left)


ST = {"p": _style("p"), "small": _style("small", 8, color=SLATE), "h1": _style("h1", 15, "Sans-B", color=GREEN, after=6),
      "h2": _style("h2", 11.5, "Sans-B", color=SLATE, after=4), "h3": _style("h3", 9.8, "Sans-B", after=2),
      "li": _style("li", left=10), "mono": _style("mono", 8.2, "Mono")}


def _fit(s, font, size, maxw):
    s = str(s)
    while size > 5.2 and pdfmetrics.stringWidth(s, font, size) > maxw:
        size -= 0.2
    return s, size


def table(header, rows, widths, size=8.2, align=None, zebra=True, bold_first=False, flags=None):
    """Table whose cells never wrap. `widths` in mm; `align` string like 'lrrl'; `flags` {(row, col): colour}."""
    ws = [w * mm for w in widths]
    data = [[Paragraph(f"<b>{h}</b>", _style("th", size, "Sans", color=white, after=0)) for h in header]] if header else []
    for r in rows:
        line = []
        for j, v in enumerate(r):
            font = "Sans-B" if (bold_first and j == 0) else "Sans"
            s, sz = _fit(v, font, size, ws[j] - 4)
            line.append(Paragraph(s.replace("&", "&amp;") if "<" not in s else s,
                                  _style("td", sz, font, after=0, color=black)))
        data.append(line)
    t = Table(data, colWidths=ws, repeatRows=1 if header else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), GREEN))
    if zebra:
        for i in range(1 + bool(header) - 1, len(data)):
            if (i - bool(header)) % 2 == 1:
                cmds.append(("BACKGROUND", (0, i), (-1, i), HexColor("#F4F8F6")))
    if align:
        for j, a in enumerate(align):
            if a == "r":
                cmds.append(("ALIGN", (j, 0), (j, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    return t


def kv(pairs, widths=(42, 128), size=9):
    return table(None, [(f"<b>{k}</b>", v) for k, v in pairs], list(widths), size=size, zebra=False)


def build(path: Path, ref: str, blocks: list, banner: str | None = None, land: bool = False, title: str = ""):
    """blocks: ('h1'|'h2'|'h3'|'p'|'small'|'li'|'mono', text) · ('table', Table) · ('sp', mm) · ('pb',)."""
    size = landscape(A4) if land else A4
    W, H = size

    def cv(*a, **kw):
        kw.setdefault("pageCompression", 1)
        return _Canvas(*a, banner=banner, doc_ref=ref, **kw)

    top = 26 * mm if banner else 19 * mm
    doc = BaseDocTemplate(str(path), pagesize=size, title=title or ref, author=HOSPITAL, creator="CH Saint-Aubin DPI",
                          producer="CH Saint-Aubin DPI", leftMargin=15 * mm, rightMargin=15 * mm, invariant=1)
    doc.addPageTemplates([PageTemplate("p", [Frame(15 * mm, 16 * mm, W - 30 * mm, H - top - 16 * mm, id="f",
                                                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])
    flow = []
    for b in blocks:
        k = b[0]
        if k == "table":
            flow.append(b[1])
            flow.append(Spacer(1, 3 * mm))
        elif k == "sp":
            flow.append(Spacer(1, b[1] * mm))
        elif k == "pb":
            flow.append(PageBreak())
        elif k == "li":
            flow.append(Paragraph("&bull; " + b[1], ST["li"]))
        else:
            flow.append(Paragraph(b[1], ST[k]))
    doc.build(flow, canvasmaker=cv)
