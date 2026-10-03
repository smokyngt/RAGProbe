"""Agrégation des traces -> Summary."""
from __future__ import annotations

import statistics
from typing import Sequence

from ..models import FailureType, RunMetadata, Summary, Trace

QA_KEYS = ("exact_match", "token_f1")
JUDGE_KEYS = ("correctness", "completeness", "groundedness")


def percentile(values: Sequence[float], q: float) -> float:
    """Percentile q∈[0,100], interpolation linéaire."""
    if not values:
        return 0.0
    s = sorted(values)
    pos = (len(s) - 1) * q / 100
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def failure_analysis(traces: Sequence[Trace]) -> dict:
    """Table 2×2 (preuves retrouvées × réponse correcte) et répartition des mauvaises réponses."""
    ev = [t for t in traces if t.analysis and t.analysis.retrieval_ok is not None]  # answerable, no pipeline error
    unans = [t for t in traces if t.analysis and t.analysis.retrieval_ok is None]
    cell = lambda ok, good: sum(t.analysis.retrieval_ok == ok and t.analysis.answer_correct == good for t in ev)
    ok_good, ok_bad, miss_good, miss_bad = cell(True, True), cell(True, False), cell(False, True), cell(False, False)
    wrong = ok_bad + miss_bad
    return {
        "n_evaluated": len(ev),
        "retrieval_ok_answer_correct": ok_good,
        "retrieval_ok_answer_wrong": ok_bad,
        "retrieval_missed_answer_correct": miss_good,
        "retrieval_missed_answer_wrong": miss_bad,
        "answer_accuracy_when_retrieval_ok": _rate(ok_good, ok_good + ok_bad),
        "answer_accuracy_when_retrieval_missed": _rate(miss_good, miss_good + miss_bad),
        "n_wrong_answers": wrong,
        "wrong_answers_due_to_retrieval": _rate(miss_bad, wrong),
        "wrong_answers_due_to_generation": _rate(ok_bad, wrong),
        "n_unanswerable": len(unans),
        "unanswerable_correctly_abstained": sum(t.analysis.answer_correct for t in unans),
    }


def aggregate(traces: Sequence[Trace], meta: RunMetadata) -> Summary:
    metric_keys = list(dict.fromkeys(k for t in traces for k in t.metrics))  # union: unanswerable traces lack retrieval keys
    retrieval_keys = [k for k in metric_keys if k not in QA_KEYS]
    judged = [t.judge for t in traces if t.judge]
    latencies = [t.latency_ms for t in traces if t.latency_ms is not None]
    counts = {f.value: 0 for f in FailureType}
    for t in traces:
        counts[t.diagnosis.value] += 1
    return Summary(
        run=meta,
        n_questions=len(traces),
        n_errors=counts[FailureType.PIPELINE_ERROR.value],
        # retrieval averaged over the questions that have something to retrieve (pipeline errors count as 0)
        retrieval={k: _mean([t.metrics[k] for t in traces if k in t.metrics]) for k in retrieval_keys},
        qa={k: _mean([t.metrics[k] for t in traces]) for k in QA_KEYS if k in metric_keys},
        judge={k: _mean([getattr(j, k) for j in judged]) for k in JUDGE_KEYS} if judged else None,
        n_judged=len(judged),
        latency_ms={"mean": _mean(latencies), "p50": percentile(latencies, 50), "p95": percentile(latencies, 95)}
        if latencies else {},
        diagnosis=counts,
        failure_analysis=failure_analysis(traces),
    )
