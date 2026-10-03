"""Diagnostic d'échec : l'information n'a pas été trouvée, ou elle n'a pas été exploitée ?

    retrieval_ok ──non──► (réponse fausse) RETRIEVAL_FAILURE
         │oui
         └────────────► (réponse fausse) GENERATION_FAILURE
                        (réponse juste mais non soutenue) GROUNDING_FAILURE
                        sinon SUCCESS

`retrieval_ok` exige TOUTES les preuves annotées dans le top-K max (multi-hop compris).
Question sans réponse possible : rien à retrouver, une réponse inventée compte comme GENERATION_FAILURE.
Règles volontairement simples et lisibles ; les faits bruts restent dans `trace.analysis`.
"""
from __future__ import annotations

from ..models import FailureType


def diagnose(retrieval_ok: bool, answer_correct: bool, grounded: bool | None) -> FailureType:
    if not answer_correct:
        return FailureType.GENERATION_FAILURE if retrieval_ok else FailureType.RETRIEVAL_FAILURE
    if grounded is False:
        return FailureType.GROUNDING_FAILURE
    return FailureType.SUCCESS
