"""Analyse d'erreurs : afficher les pires traces selon une métrique."""
from __future__ import annotations

from typing import Sequence

from ..models import FailureType, Trace

JUDGE_DIMS = ("correctness", "completeness", "groundedness")


def metric_value(t: Trace, metric: str) -> float | None:
    if metric in JUDGE_DIMS:
        return getattr(t.judge, metric) if t.judge else None
    return t.metrics.get(metric)


def available_metrics(traces: Sequence[Trace]) -> list[str]:
    names = list(dict.fromkeys(k for t in traces for k in t.metrics))
    return names + (list(JUDGE_DIMS) if any(t.judge for t in traces) else [])


def worst(traces: Sequence[Trace], metric: str, n: int, failure_type: FailureType | None = None) -> list[Trace]:
    if metric not in available_metrics(traces):
        raise ValueError(f"unknown metric '{metric}'; available: {available_metrics(traces)}")
    pool = [t for t in traces if (failure_type is None or t.diagnosis == failure_type)
            and metric_value(t, metric) is not None]
    return sorted(pool, key=lambda t: (metric_value(t, metric), t.question_id))[:n]


def format_trace(t: Trace, metric: str, rank: int) -> str:
    out = [f"#{rank} {t.question_id}  {metric}={metric_value(t, metric):.3f}  [{t.diagnosis.value}]",
           f"  Q        : {t.input.question}",
           f"  reference: {t.ground_truth.answer}"]
    if t.error:
        out.append(f"  ERROR    : {t.error}")
        return "\n".join(out)
    po = t.pipeline_output
    gt = t.ground_truth
    expected = ([f"{e.document_id} p.{e.page}" for e in gt.evidence] or gt.relevant_chunks) if gt.answerable \
        else "nothing (unanswerable: an abstention is expected)"
    got = [c.chunk_id + (f" ({c.document_id} p.{c.page})" if c.document_id and c.page else "") for c in po.retrieved_chunks[:5]]
    out += [f"  answer   : {po.answer}",
            f"  expected : {expected}",
            f"  top-5    : {got}"]
    if t.judge:
        out.append(f"  judge    : corr={t.judge.correctness:.2f} compl={t.judge.completeness:.2f} "
                   f"ground={t.judge.groundedness:.2f} — {t.judge.reason}")
    if t.judge_error:
        out.append(f"  judge ERR: {t.judge_error}")
    return "\n".join(out)
