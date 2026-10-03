"""Benchmark runner : dataset -> pipeline -> métriques -> traces -> summary. Ne connaît pas la pipeline."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import Config
from .dataset import Dataset
from .evaluation.diagnosis import diagnose
from .evaluation.judge import AnswerJudge
from .evaluation.qa import evaluate_answer
from .evaluation.retrieval import dedupe, evaluate_retrieval, recall_at_k
from .models import (FailureType, JudgeScores, RunMetadata, Sample, Summary, Trace, TraceAnalysis,
                     TraceGroundTruth, TraceInput, TracePipelineOutput)
from .pipelines.base import PipelineAdapter
from .reporting.aggregator import aggregate
from .storage import TraceWriter, write_summary

log = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(self, config: Config, adapter: PipelineAdapter, judge: AnswerJudge | None = None):
        self.cfg, self.adapter, self.judge = config, adapter, judge

    def evaluate_sample(self, sample: Sample) -> Trace:
        bench = self.cfg.benchmark
        base = dict(
            question_id=sample.id,
            input=TraceInput(question=sample.question),
            ground_truth=TraceGroundTruth(answer=sample.reference_answer, relevant_chunks=sample.relevant_chunks,
                                          document_id=sample.document_id, metadata=sample.metadata),
        )
        try:
            result = self.adapter.query(sample.question)
        except Exception as e:  # une panne sur une question ne doit pas arrêter le run
            log.warning("%s: pipeline error: %s", sample.id, e)
            # métriques à zéro : une pipeline qui plante n'est pas "meilleure" qu'une qui se trompe
            metrics = evaluate_retrieval([], sample.relevant_chunks, bench.top_k, bench.retrieval_metrics)
            metrics |= evaluate_answer("", sample.reference_answer)
            return Trace(**base, metrics=metrics, diagnosis=FailureType.PIPELINE_ERROR,
                         error=f"{type(e).__name__}: {e}")

        ids = [c.chunk_id for c in result.retrieved_chunks]
        metrics = evaluate_retrieval(ids, sample.relevant_chunks, bench.top_k, bench.retrieval_metrics)
        metrics |= evaluate_answer(result.answer, sample.reference_answer)

        judge_scores: JudgeScores | None = None
        judge_error: str | None = None
        if self.judge:
            evidence = [c.text for c in result.retrieved_chunks if c.text][: self.cfg.judge.max_evidence_chunks]
            try:
                judge_scores = self.judge.evaluate(sample.question, sample.reference_answer, result.answer, evidence)
            except Exception as e:
                judge_error = f"{type(e).__name__}: {e}"
                log.warning("%s: judge failed: %s", sample.id, judge_error)

        retrieval_ok = recall_at_k(dedupe(ids), set(sample.relevant_chunks), max(bench.top_k)) >= 1.0
        if judge_scores:
            answer_correct, source = judge_scores.correctness >= bench.judge_correct_threshold, "judge"
            grounded: bool | None = judge_scores.groundedness >= bench.grounded_threshold
        else:
            answer_correct, source = metrics["token_f1"] >= bench.answer_correct_f1_threshold, "token_f1"
            grounded = None
        return Trace(
            **base,
            pipeline_output=TracePipelineOutput(answer=result.answer, retrieved_chunks=result.retrieved_chunks),
            metrics=metrics, judge=judge_scores, judge_error=judge_error,
            analysis=TraceAnalysis(retrieval_ok=retrieval_ok, answer_correct=answer_correct,
                                   answer_correct_source=source, grounded=grounded),
            diagnosis=diagnose(retrieval_ok, answer_correct, grounded),
            latency_ms=result.latency_ms,
        )

    def run(self, dataset: Dataset, run_id: str, run_dir: Path) -> Summary:
        meta = RunMetadata(
            run_id=run_id, timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            pipeline=self.adapter.name, pipeline_version=self.adapter.version,
            dataset=dataset.name, dataset_version=dataset.version, dataset_sha256=dataset.sha256,
            n_questions=len(dataset.samples), ragbench_version=__version__, configuration=self.cfg.redacted(),
        )
        traces: list[Trace] = []
        n = len(dataset.samples)
        with TraceWriter(run_dir) as writer:
            for i, sample in enumerate(dataset.samples, 1):
                trace = self.evaluate_sample(sample)
                writer.write(trace)
                traces.append(trace)
                log.info("[%d/%d] %s %s %s", i, n, sample.id, trace.diagnosis.value,
                         f"f1={trace.metrics['token_f1']:.2f}" + (f" {trace.latency_ms:.0f}ms" if trace.latency_ms else ""))
        summary = aggregate(traces, meta)
        write_summary(run_dir, summary)
        return summary
