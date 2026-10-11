"""Shared helpers for AccountingBench: money, dates, number formats, IBANs."""
from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENT = Decimal("0.01")


def D(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT, ROUND_HALF_UP)


def q2(x: Decimal) -> Decimal:
    return x.quantize(CENT, ROUND_HALF_UP)


def date(d: int, m: int, y: int = 2026) -> dt.date:
    return dt.date(y, m, d)


def is_business_day(d: dt.date) -> bool:
    return d.weekday() < 5


def prev_business_day(d: dt.date) -> dt.date:
    while not is_business_day(d):
        d -= dt.timedelta(days=1)
    return d


# ---------- number formats (as printed in the documents) ----------

def _group(intpart: str, sep: str) -> str:
    out = []
    while len(intpart) > 3:
        out.insert(0, intpart[-3:])
        intpart = intpart[:-3]
    out.insert(0, intpart)
    return sep.join(out)


def fmt(x: Decimal, style: str = "en") -> str:
    """en: 15,360.00 · fr: 15 360,00 · de: 15.360,00 · ch: 15'360.00"""
    x = q2(Decimal(x))
    neg = x < 0
    s = f"{abs(x):.2f}"
    i, f = s.split(".")
    if style == "en":
        out = _group(i, ",") + "." + f
    elif style == "fr":
        out = _group(i, " ") + "," + f
    elif style == "de":
        out = _group(i, ".") + "," + f
    else:
        raise ValueError(style)
    return ("-" if neg else "") + out


def accept_amount(x: Decimal) -> list[str]:
    """Equivalent printed forms of an amount, for key-fact matching."""
    x = q2(Decimal(x))
    forms = [fmt(x, "en"), fmt(x, "fr"), fmt(x, "de"), f"{x:.2f}"]
    if x == x.to_integral():
        forms += [_group(str(abs(int(x))), ","), str(abs(int(x)))]
    out = []
    for f in forms:
        if f not in out:
            out.append(f)
    return out


def fdate(d: dt.date, style: str = "slash") -> str:
    if style == "slash":
        return d.strftime("%d/%m/%Y")
    if style == "dot":
        return d.strftime("%d.%m.%Y")
    if style == "dash":
        return d.strftime("%d-%m-%Y")
    if style == "long":
        return f"{d.day} {d.strftime('%B %Y')}"
    if style == "fr_long":
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                "novembre", "décembre"]
        return f"{d.day} {mois[d.month - 1]} {d.year}"
    if style == "iso":
        return d.isoformat()
    raise ValueError(style)


def accept_date(d: dt.date) -> list[str]:
    return [fdate(d, "slash"), fdate(d, "iso"), fdate(d, "dot"), fdate(d, "long"), d.strftime("%d %b %Y"),
            f"{d.strftime('%B')} {d.day}, {d.year}"]


# ---------- IBAN ----------

def _mod97(s: str) -> int:
    n = "".join(str(int(c, 36)) for c in s)
    return int(n) % 97


def iban(country: str, bban: str) -> str:
    """Valid IBAN (ISO 13616 check digits) from a country code and a BBAN."""
    bban = bban.replace(" ", "").upper()
    check = 98 - _mod97(bban + country + "00")
    raw = f"{country}{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def iban_valid(value: str) -> bool:
    s = value.replace(" ", "").upper()
    return _mod97(s[4:] + s[:4]) == 1
