"""Générateurs de dorks : objectif en langage naturel -> requête à opérateurs."""
from __future__ import annotations

import re
from typing import Callable, Protocol

from .metrics import normalize_answer


class DorkGenerator(Protocol):
    name: str

    def generate(self, goal: str) -> str: ...


_DOMAIN = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:gouv\.fr|fr|com|org|eu|net|example))\b", re.I)
_FILETYPES = {"pdf": "pdf", "word": "docx", "docx": "docx", "excel": "xlsx", "powerpoint": "pptx", "pptx": "pptx", "xlsx": "xlsx", "csv": "csv"}


class RuleBasedGenerator:
    """Baseline sans LLM : domaine -> site:, format -> filetype:, citations -> phrases, reste -> mots-clés."""

    name = "rule-based"

    def generate(self, goal: str) -> str:
        parts, rest = [], goal
        if m := _DOMAIN.search(rest):
            parts.append(f"site:{m.group(1).lower()}")
            rest = rest.replace(m.group(0), " ")
        for kw, ft in _FILETYPES.items():
            if re.search(rf"\b{kw}\b", rest, re.I):
                parts.append(f"filetype:{ft}")
                rest = re.sub(rf"\b{kw}\b", " ", rest, flags=re.I)
                break
        for q in re.findall(r"[«\"]([^»\"]+)[»\"]", rest):
            parts.append(f'"{q.strip()}"')
        rest = re.sub(r"[«\"][^»\"]+[»\"]", " ", rest)
        for ex in re.findall(r"\bsans\s+(\w+)", rest, re.I):
            parts.append(f"-{ex.lower()}")
        rest = re.sub(r"\bsans\s+\w+", " ", rest, flags=re.I)
        stop = {"trouver", "cherche", "chercher", "document", "documents", "modele", "sur", "pour", "dans", "avec", "tout"}
        words = [w for w in normalize_answer(rest).split() if len(w) > 2 and w not in stop]
        return " ".join(parts + words)


PROMPT = """Transforme cet objectif de recherche en UNE requête Google avec opérateurs
(site:, filetype:, intitle:, inurl:, "phrase exacte", -exclusion). Uniquement des documents publics.
Réponds avec la requête seule, sans explication.

Objectif : {goal}"""


class LLMGenerator:
    def __init__(self, complete: Callable[[str], str], name: str = "llm"):
        self.complete, self.name = complete, name

    def generate(self, goal: str) -> str:
        out = self.complete(PROMPT.format(goal=goal)).strip()
        return out.strip("`").splitlines()[0].strip() if out else ""
