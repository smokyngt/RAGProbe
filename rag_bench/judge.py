"""LLM-as-a-judge : évalue la réponse produite par la pipeline (ne répond pas à la question)."""
from __future__ import annotations

import json
import re
from typing import Callable

PROMPT = """Tu es un évaluateur strict. Tu NE réponds PAS à la question : tu évalues la RÉPONSE DU MODÈLE.

QUESTION
{question}

RÉPONSE DE RÉFÉRENCE
{reference}

RÉPONSE DU MODÈLE
{answer}

EVIDENCE (passages de référence)
{evidence}

PASSAGES RÉCUPÉRÉS PAR LA PIPELINE
{retrieved}

Note chaque critère de 0 à 1 :
- correctness : la réponse du modèle est équivalente à la référence (même si formulée autrement)
- completeness : tous les éléments de la référence sont présents
- groundedness : chaque affirmation est supportée par les passages récupérés
- citation_correctness : les sources citées (le cas échéant) soutiennent bien la réponse ; 1 si aucune citation attendue

Réponds UNIQUEMENT par un JSON : {{"correctness": x, "completeness": x, "groundedness": x, "citation_correctness": x, "comment": "..."}}"""

CRITERIA = ("correctness", "completeness", "groundedness", "citation_correctness")


class LLMJudge:
    """`complete` : prompt -> texte. Découplé du fournisseur pour rester testable."""

    def __init__(self, complete: Callable[[str], str]):
        self.complete = complete

    def evaluate(self, question, reference, answer, evidence: list[str], retrieved: list[str]) -> dict:
        prompt = PROMPT.format(
            question=question,
            reference=reference,
            answer=answer or "(vide)",
            evidence="\n---\n".join(evidence) or "(aucune)",
            retrieved="\n---\n".join(retrieved) or "(aucun)",
        )
        raw = self.complete(prompt)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"error": "judge: JSON introuvable", "raw": raw}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"error": "judge: JSON invalide", "raw": raw}
        return {c: float(data.get(c, 0.0)) for c in CRITERIA} | {"comment": data.get("comment", "")}


def anthropic_complete(model: str = "claude-sonnet-5-5", max_tokens: int = 512) -> Callable[[str], str]:
    """Fabrique un `complete` via le SDK Anthropic (clé dans ANTHROPIC_API_KEY)."""
    import anthropic  # import paresseux : dépendance optionnelle

    client = anthropic.Anthropic()

    def complete(prompt: str) -> str:
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    return complete
