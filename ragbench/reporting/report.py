"""Rapport texte d'un run, et comparaison de deux runs."""
from __future__ import annotations

from ..models import Summary

BAR = "=" * 28


def _label(key: str) -> str:
    if key == "mrr":
        return "MRR"
    name, _, k = key.partition("_at_")
    pretty = {"recall": "Recall", "precision": "Precision", "ndcg": "nDCG"}.get(name, name)
    return f"{pretty}@{k}" if k else pretty


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def _dur(ms: float) -> str:
    return f"{ms / 1000:.2f}s" if ms >= 1000 else f"{ms:.0f}ms"


def format_report(s: Summary) -> str:
    r = s.run
    lines = [BAR, "BENCHMARK RESULTS", BAR, "",
             f"Run:       {r.run_id}",
             f"Pipeline:  {r.pipeline} ({r.pipeline_version})",
             f"Dataset:   {r.dataset} ({r.dataset_version}, sha256 {r.dataset_sha256[:8]})",
             f"Questions: {s.n_questions}" + (f"   ⚠ pipeline errors: {s.n_errors} (counted as 0)" if s.n_errors else ""),
             "", "RETRIEVAL", ""]
    lines += [f"{_label(k):<16}{v:.2f}" for k, v in s.retrieval.items()]
    lines += ["", "QA", ""]
    lines += [f"{'Exact Match' if k == 'exact_match' else 'Token F1':<16}{v:.2f}" for k, v in s.qa.items()]
    if s.judge:
        lines += ["", f"LLM JUDGE  (n={s.n_judged}/{s.n_questions})", ""]
        lines += [f"{k.capitalize():<16}{v:.2f}" for k, v in s.judge.items()]
    if s.latency_ms:
        lines += ["", "LATENCY", ""]
        lines += [f"{'Mean' if k == 'mean' else k:<16}{_dur(v)}" for k, v in s.latency_ms.items()]
    lines += ["", "DIAGNOSIS", ""]
    lines += [f"{k:<22}{v}" for k, v in s.diagnosis.items() if v]
    f = s.failure_analysis
    lines += ["", "WHY DO ANSWERS FAIL?", "",
              f"{'':<26}{'answer correct':>16}{'answer wrong':>14}",
              f"{'evidence retrieved':<26}{f['retrieval_ok_answer_correct']:>16}{f['retrieval_ok_answer_wrong']:>14}",
              f"{'evidence missing':<26}{f['retrieval_missed_answer_correct']:>16}{f['retrieval_missed_answer_wrong']:>14}",
              "",
              f"Accuracy when evidence retrieved : {_pct(f['answer_accuracy_when_retrieval_ok'])}",
              f"Accuracy when evidence missing   : {_pct(f['answer_accuracy_when_retrieval_missed'])}"]
    if f["n_wrong_answers"]:
        lines += [f"Wrong answers ({f['n_wrong_answers']}): {_pct(f['wrong_answers_due_to_retrieval'])} retrieval failure, "
                  f"{_pct(f['wrong_answers_due_to_generation'])} generation failure"]
    return "\n".join(lines)


def format_comparison(a: Summary, b: Summary) -> str:
    notes = []
    if a.run.dataset_sha256 != b.run.dataset_sha256:
        notes.append("⚠ different datasets (hash): comparison is not rigorous")
    rows = [f"{'metric':<22}{a.run.run_id[-22:]:>24}{b.run.run_id[-22:]:>24}{'delta':>9}"]
    for section in ("retrieval", "qa", "judge"):
        da, db = getattr(a, section) or {}, getattr(b, section) or {}
        for k in da:
            if k in db:
                rows.append(f"{_label(k):<22}{da[k]:>24.3f}{db[k]:>24.3f}{db[k] - da[k]:>+9.3f}")
    if a.latency_ms and b.latency_ms:
        for k in ("p50", "p95"):
            rows.append(f"{'latency ' + k + ' (ms)':<22}{a.latency_ms[k]:>24.0f}{b.latency_ms[k]:>24.0f}"
                        f"{b.latency_ms[k] - a.latency_ms[k]:>+9.0f}")
    return "\n".join(notes + rows)
