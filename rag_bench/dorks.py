"""Google dorking : parsing/validation de requêtes à opérateurs + moteur de recherche simulé.

Périmètre : recherche de documents PUBLICS (contrats-types, textes officiels, rapports).
Le moteur simulé permet un benchmark déterministe et hors ligne ; un vrai moteur se branche via `SearchEngine`.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

OPERATORS = {"site", "filetype", "ext", "intitle", "inurl", "intext", "before", "after"}
_TOKEN = re.compile(r'(?P<neg>-)?(?:(?P<op>[a-z]+):(?P<val>"[^"]*"|\S+)|(?P<phrase>"[^"]*")|(?P<word>\S+))')


@dataclass
class Clause:
    op: str | None  # None = terme libre / phrase
    value: str
    negated: bool = False
    phrase: bool = False


@dataclass
class Dork:
    raw: str
    clauses: list[Clause] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors and any(not c.negated for c in self.clauses)

    def has(self, op: str, value: str | None = None) -> bool:
        return any(
            c.op == op and not c.negated and (value is None or c.value.lower() == value.lower())
            for c in self.clauses
        )


def parse(raw: str) -> Dork:
    d = Dork(raw=raw)
    if raw.count('"') % 2:
        d.errors.append("guillemets non fermés")
    for m in _TOKEN.finditer(raw):
        neg = bool(m["neg"])
        if m["op"]:
            if m["op"] not in OPERATORS:
                d.errors.append(f"opérateur inconnu: {m['op']}")
                continue
            val = m["val"].strip('"')
            if not val:
                d.errors.append(f"valeur vide pour {m['op']}:")
                continue
            d.clauses.append(Clause(m["op"], val, neg, phrase=m["val"].startswith('"')))
        elif m["phrase"]:
            d.clauses.append(Clause(None, m["phrase"].strip('"'), neg, phrase=True))
        elif m["word"] not in ("OR", "AND"):  # OR traité comme séparateur souple (V0)
            d.clauses.append(Clause(None, m["word"], neg))
    return d


@dataclass
class Page:
    url: str
    title: str
    text: str

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc.lower()

    @property
    def ext(self) -> str:
        path = urlparse(self.url).path
        return path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else "html"


class SearchEngine(Protocol):
    def search(self, query: str, k: int = 10) -> list[str]: ...  # urls classées


def _fold(s: str) -> str:
    """Minuscules sans accents : la recherche simulée est insensible aux accents."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _match(c: Clause, p: Page) -> bool:
    v = _fold(c.value)
    if c.op == "site":
        return p.host == v or p.host.endswith("." + v)
    if c.op in ("filetype", "ext"):
        return p.ext == v.lstrip(".")
    if c.op == "intitle":
        return v in _fold(p.title)
    if c.op == "inurl":
        return v in p.url.lower()
    if c.op == "intext":
        return v in _fold(p.text)
    if c.op in ("before", "after"):
        return True  # dates non modélisées en V0
    return v in _fold(p.title + " " + p.text)


class SimulatedEngine:
    """Applique les opérateurs sur un mini-web local ; classe par fréquence des termes libres."""

    def __init__(self, pages: list[Page]):
        self.pages = pages

    def search(self, query: str, k: int = 10) -> list[str]:
        d = parse(query)
        if not d.valid:
            return []
        scored = []
        for p in self.pages:
            if any(_match(c, p) != (not c.negated) for c in d.clauses):
                continue
            blob = _fold(p.title + " " + p.text)
            free = [_fold(c.value) for c in d.clauses if c.op is None and not c.negated]
            scored.append((sum(blob.count(t) for t in free), p.url))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [u for _, u in scored[:k]]
