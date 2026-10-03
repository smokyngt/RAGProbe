import json

from rag_bench.dataset import load_corpus, load_dataset
from rag_bench.judge import LLMJudge
from rag_bench.pipelines.base import PipelineResult
from rag_bench.pipelines.bm25 import BM25Pipeline
from rag_bench.runner import compare, run_benchmark


def test_bm25_end_to_end(tmp_path):
    ex, corpus = load_dataset("data/questions.jsonl"), load_corpus("data/corpus.jsonl")
    out = tmp_path / "r.json"
    report = run_benchmark(ex, BM25Pipeline(corpus), corpus, out_path=out)
    assert report["aggregate"]["n"] == len(ex)
    assert report["aggregate"]["retrieval"]["recall@10"] >= 0.8
    assert json.loads(out.read_text())["pipeline"] == "bm25-extractive"
    assert "recall@5" in compare(report, report)


class Broken:
    name = "broken"

    def run(self, q):
        raise RuntimeError("boom")


def test_pipeline_error_is_isolated():
    ex = load_dataset("data/questions.jsonl")[:2]
    rep = run_benchmark(ex, Broken())
    assert rep["aggregate"]["n_errors"] == 2
    assert rep["aggregate"]["diagnosis"] == {"pipeline_error": 2}


class Fixed:
    name = "fixed"

    def run(self, q):
        return PipelineResult("Le chiffre d affaires 2025 est de 1 250 millions d euros.", ["alpha_ra2025_01"])


def test_judge_overrides_f1():
    ex = load_dataset("data/questions.jsonl")[:1]
    corpus = load_corpus("data/corpus.jsonl")
    judge = LLMJudge(lambda p: 'ok {"correctness":1,"completeness":1,"groundedness":1,"citation_correctness":1,"comment":"x"}')
    rep = run_benchmark(ex, Fixed(), corpus, judge)
    assert rep["results"][0]["diagnosis"] == "ok"
    assert rep["aggregate"]["judge"]["correctness"] == 1.0
