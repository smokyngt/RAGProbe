"""CLI :  python -m rag_bench run|compare ..."""
from __future__ import annotations

import argparse
import json
import sys

from .dataset import load_corpus, load_dataset
from .judge import LLMJudge, anthropic_complete
from .pipelines.bm25 import BM25Pipeline
from .dork_bench import load_pages, run_dork_benchmark
from .dork_gen import LLMGenerator, RuleBasedGenerator
from .dorks import SimulatedEngine
from .pipelines.http import HttpPipeline
from .report import write_report
from .runner import compare, run_benchmark


def _print_summary(report: dict) -> None:
    a = report["aggregate"]
    print(f"\n== {report['pipeline']}  (n={a['n']}, erreurs={a['n_errors']}) ==")
    for section in ("retrieval", "qa", "judge"):
        if section in a:
            print(f"[{section}] " + "  ".join(f"{k}={v:.3f}" for k, v in a[section].items()))
    print("[diagnostic] " + "  ".join(f"{k}={v}" for k, v in sorted(a["diagnosis"].items())))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rag_bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="lancer le benchmark")
    r.add_argument("--dataset", default="data/questions.jsonl")
    r.add_argument("--corpus", default="data/corpus.jsonl")
    r.add_argument("--pipeline", choices=["bm25", "http"], default="bm25")
    r.add_argument("--url", help="endpoint de la pipeline (--pipeline http)")
    r.add_argument("--judge", action="store_true", help="LLM-as-a-judge (ANTHROPIC_API_KEY requis)")
    r.add_argument("--judge-model", default="claude-sonnet-5-5")
    r.add_argument("--out", default="results/results.json")

    d = sub.add_parser("dork", help="benchmark de génération de dorks (moteur simulé hors ligne)")
    d.add_argument("--tasks", default="data/dork_tasks.jsonl")
    d.add_argument("--web", default="data/web.jsonl")
    d.add_argument("--generator", choices=["rule", "llm"], default="rule")
    d.add_argument("--model", default="claude-sonnet-5-5")
    d.add_argument("--out", default="results/dork.json")

    rp = sub.add_parser("report", help="rapport HTML depuis des results.json")
    rp.add_argument("results", nargs="+")
    rp.add_argument("--out", default="results/report.html")

    c = sub.add_parser("compare", help="comparer deux results.json")
    c.add_argument("baseline")
    c.add_argument("candidate")

    args = p.parse_args(argv)
    if args.cmd == "compare":
        load = lambda f: json.load(open(f, encoding="utf-8"))
        print(compare(load(args.baseline), load(args.candidate)))
        return 0

    if args.cmd == "report":
        write_report(args.results, args.out)
        print(f"rapport : {args.out}")
        return 0
    if args.cmd == "dork":
        from .dataset import load_jsonl
        gen = RuleBasedGenerator() if args.generator == "rule" else LLMGenerator(anthropic_complete(args.model), "llm-" + args.model)
        rep = run_dork_benchmark(load_jsonl(args.tasks), gen, SimulatedEngine(load_pages(args.web)), args.out)
        a = rep["aggregate"]
        print(f"== dorking / {rep['pipeline']} (n={a['n']}) ==")
        print("[status] " + "  ".join(f"{k}={v}" for k, v in a["status"].items()))
        print("[metrics] " + "  ".join(f"{k}={a[k]:.3f}" for k in ("syntax_valid", "constraint_score", "recall@5", "precision@5", "mrr")))
        for r in rep["results"]:
            print(f"  {r['id']} {r['status']:<9} {r.get('query', r.get('error'))}")
        return 0

    examples = load_dataset(args.dataset)
    corpus = load_corpus(args.corpus)
    if args.pipeline == "http":
        if not args.url:
            p.error("--url requis avec --pipeline http")
        pipeline = HttpPipeline(args.url)
    else:
        pipeline = BM25Pipeline(corpus)
    judge = LLMJudge(anthropic_complete(args.judge_model)) if args.judge else None

    def progress(i, n, row):
        print(f"[{i}/{n}] {row['id']}: {row['diagnosis']}", file=sys.stderr)

    report = run_benchmark(examples, pipeline, corpus, judge, args.out, progress)
    _print_summary(report)
    print(f"\nrésultats : {args.out}")
    return 0
