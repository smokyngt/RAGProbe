from rag_bench import dorks
from rag_bench.dataset import load_jsonl
from rag_bench.dork_bench import load_pages, run_dork_benchmark
from rag_bench.dork_gen import RuleBasedGenerator


def test_parse_operators():
    d = dorks.parse('site:regulateur.example filetype:pdf "covenant de levier" -blog')
    assert d.valid and d.has("site", "regulateur.example") and d.has("filetype", "pdf")
    assert any(c.negated and c.value == "blog" for c in d.clauses)


def test_parse_errors():
    assert not dorks.parse('foo:bar "oups').valid
    assert not dorks.parse("-blog").valid  # que des exclusions


def test_engine_filters():
    eng = dorks.SimulatedEngine(load_pages("data/web.jsonl"))
    urls = eng.search("site:banque-centrale.example filetype:csv taux")
    assert len(urls) == 1 and urls[0].endswith("taux-directeurs.csv")
    assert eng.search("site:regulateur.example décision") == eng.search("site:regulateur.example decision")


def test_rule_based_baseline():
    rep = run_dork_benchmark(load_jsonl("data/dork_tasks.jsonl"), RuleBasedGenerator(),
                             dorks.SimulatedEngine(load_pages("data/web.jsonl")))
    assert rep["aggregate"]["syntax_valid"] == 1.0
    assert rep["aggregate"]["status"]["pass"] >= 7
