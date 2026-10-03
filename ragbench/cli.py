"""CLI : run | report | analyze | compare."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from .config import ConfigError, load_config
from .dataset import DatasetError, load_dataset
from .evaluation.judge import JudgeError, build_judge
from .models import FailureType
from .pipelines.http import HTTPPipelineAdapter
from .reporting.analyze import available_metrics, format_trace, worst
from .reporting.report import format_comparison, format_report
from .runner import BenchmarkRunner
from .storage import RunNotFound, create_run_dir, load_summary, load_traces, slug

log = logging.getLogger("ragbench")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmark.py", description="Benchmark runner for RAG pipelines (retrieval + QA).")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--results-dir", default="results")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a benchmark")
    r.add_argument("--dataset", required=True)
    r.add_argument("--config", required=True)
    r.add_argument("--run-id", help="default: <date>_<pipeline>_<version>")
    r.add_argument("--limit", type=int, help="only evaluate the first N questions")
    r.add_argument("--no-judge", action="store_true", help="disable the judge even if the config enables it")

    rp = sub.add_parser("report", help="print the report of a run")
    rp.add_argument("--run", required=True)

    a = sub.add_parser("analyze", help="print the worst results of a run")
    a.add_argument("--run", required=True)
    a.add_argument("--metric", help="default: correctness if judged, else token_f1")
    a.add_argument("--worst", type=int, default=10)
    a.add_argument("--failure-type", choices=[f.value for f in FailureType])

    c = sub.add_parser("compare", help="compare two runs")
    c.add_argument("baseline")
    c.add_argument("candidate")
    return p


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    if args.no_judge:
        cfg.judge.enabled = False
    dataset = load_dataset(args.dataset, cfg.dataset.name, cfg.dataset.version, args.limit)
    judge = build_judge(cfg.judge)
    adapter = HTTPPipelineAdapter(cfg.pipeline)
    base_id = args.run_id or f"{date.today().isoformat()}_{slug(adapter.name)}_{slug(adapter.version)}"
    run_id, run_dir = create_run_dir(args.results_dir, base_id, explicit=bool(args.run_id))
    log.info("run %s: %d questions, pipeline=%s, judge=%s", run_id, len(dataset.samples),
             cfg.pipeline.endpoint, judge.name if judge else "off")
    summary = BenchmarkRunner(cfg, adapter, judge).run(dataset, run_id, run_dir)
    print(format_report(summary))
    print(f"\nresults: {run_dir}/summary.json, traces.jsonl")
    return 1 if summary.n_errors == summary.n_questions else 0


def cmd_report(args) -> int:
    print(format_report(load_summary(args.results_dir, args.run)))
    return 0


def cmd_analyze(args) -> int:
    traces = load_traces(args.results_dir, args.run)
    metric = args.metric or ("correctness" if any(t.judge for t in traces) else "token_f1")
    ft = FailureType(args.failure_type) if args.failure_type else None
    try:
        selected = worst(traces, metric, args.worst, ft)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"{len(selected)} worst traces on '{metric}'" + (f" (diagnosis {ft.value})" if ft else "")
          + f" — available metrics: {', '.join(available_metrics(traces))}\n")
    for i, t in enumerate(selected, 1):
        print(format_trace(t, metric, i), end="\n\n")
    return 0


def cmd_compare(args) -> int:
    print(format_comparison(load_summary(args.results_dir, args.baseline), load_summary(args.results_dir, args.candidate)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    try:
        return {"run": cmd_run, "report": cmd_report, "analyze": cmd_analyze, "compare": cmd_compare}[args.cmd](args)
    except (ConfigError, DatasetError, JudgeError, RunNotFound, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
