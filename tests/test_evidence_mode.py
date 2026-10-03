"""Evidence-based ground truth (FinanceBench): matching by document + page or by text, unanswerable questions."""
import json

from ragbench.config import Config, PipelineConfig
from ragbench.dataset import Dataset, load_dataset
from ragbench.evaluation.qa import is_abstention
from ragbench.evaluation.retrieval import covers, evidence_hits, metrics_from_hits, normalize_doc_id, text_overlap
from ragbench.models import EvidenceRef, FailureType, PipelineResult, RetrievedChunk, Sample
from ragbench.pipelines import PipelineAdapter
from ragbench.pipelines.http import parse_chunk
from ragbench.runner import BenchmarkRunner

EV = EvidenceRef(document_id="fin_doc_011", page=162, text="Profit before income taxes 5,062 5,246 … Income taxes -1,494 -1,540")


def chunk(cid, doc=None, page=None, page_end=None, text=None):
    return RetrievedChunk(chunk_id=cid, document_id=doc, page=page, page_end=page_end, text=text)


def test_doc_id_normalisation():
    assert normalize_doc_id("corpus/documents/fin_doc_011.pdf") == normalize_doc_id("FIN_DOC_011") == "fin_doc_011"


def test_covers_by_page_and_range():
    assert covers(chunk("a", "fin_doc_011.pdf", 162), EV)
    assert covers(chunk("a", "fin_doc_011", 160, 163), EV)
    assert not covers(chunk("a", "fin_doc_011", 161), EV)  # neighbouring page, no text
    assert not covers(chunk("a", "fin_doc_012", 162), EV)  # same page number, other document


def test_covers_by_text_when_page_unknown():
    txt = "Consolidated income statement. Profit before income taxes 5,062 5,246. Income taxes -1,494 -1,540."
    assert text_overlap(EV.text, txt) == 1.0
    assert covers(chunk("a", "fin_doc_011", None, text=txt), EV)
    assert covers(chunk("a", None, None, text=txt), EV)  # no document id: stricter threshold, still met
    assert not covers(chunk("a", "fin_doc_012", None, text=txt), EV)  # explicit other document: never a match
    assert not covers(chunk("a", "fin_doc_011", None, text="Revenue grew strongly in 2025."), EV)


def test_metrics_with_multiple_evidence_and_duplicates():
    evs = [EV, EvidenceRef(document_id="fin_doc_011", page=56)]
    got = [chunk("x", "fin_doc_001", 3), chunk("a", "fin_doc_011", 162), chunk("a", "fin_doc_011", 162), chunk("b", "fin_doc_011", 56)]
    hits = evidence_hits(got, evs)
    assert [sorted(h) for h in hits] == [[], [0], [1]]  # duplicate chunk "a" counted once
    m = metrics_from_hits(hits, len(evs), [1, 2, 3], ["recall", "mrr", "precision"])
    assert m["recall_at_1"] == 0 and m["recall_at_2"] == 0.5 and m["recall_at_3"] == 1.0
    assert m["mrr"] == 0.5 and m["precision_at_2"] == 0.5


def test_abstention_detection():
    assert is_abstention("This cannot be established from the available documents.")
    assert is_abstention("The report does not disclose a 2027 budget.")
    assert not is_abstention("The 2027 budget shows a net loss of EUR 7.7 million.")


def test_parse_chunk_with_provenance():
    c = parse_chunk({"id": 7, "content": "t", "source": "fin_doc_003.pdf", "page_number": "12", "page_end": 13})
    assert (c.chunk_id, c.document_id, c.page, c.page_end, c.text) == ("7", "fin_doc_003.pdf", 12, 13, "t")


def test_sample_requires_ground_truth_unless_unanswerable():
    import pytest
    with pytest.raises(ValueError):
        Sample(id="q", question="q?", reference_answer="r")
    s = Sample(id="q", question="q?", reference_answer="cannot be established", metadata={"answerable": False})
    assert s.answerable is False


class Fake(PipelineAdapter):
    name, version = "fake", "v0"

    def __init__(self, script):
        self.script = script

    def query(self, question):
        answer, chunks = self.script[question]
        return PipelineResult(answer=answer, retrieved_chunks=chunks, latency_ms=5.0)


def test_runner_evidence_and_unanswerable(tmp_path):
    samples = [
        Sample(id="a", question="Q1", reference_answer="29.4%", evidence=[EV]),
        Sample(id="b", question="Q2", reference_answer="29.4%", evidence=[EV]),
        Sample(id="c", question="Q3", reference_answer="Cannot be established.", metadata={"answerable": False}),
        Sample(id="d", question="Q4", reference_answer="Cannot be established.", metadata={"answerable": False}),
    ]
    script = {
        "Q1": ("29.4%", [chunk("k", "fin_doc_011.pdf", 162)]),         # evidence found, right answer
        "Q2": ("12%", [chunk("k", "fin_doc_012.pdf", 162)]),           # wrong document -> retrieval failure
        "Q3": ("This cannot be established from the documents.", []),  # correct abstention
        "Q4": ("It was EUR 4 million.", [chunk("z", "fin_doc_015", 10)]),  # invented answer
    }
    cfg = Config(pipeline=PipelineConfig(name="fake", endpoint="http://unused"))
    (tmp_path / "run").mkdir()
    s = BenchmarkRunner(cfg, Fake(script)).run(Dataset("d", "v", tmp_path / "d.jsonl", "h", samples), "run", tmp_path / "run")
    assert s.diagnosis["SUCCESS"] == 2 and s.diagnosis["RETRIEVAL_FAILURE"] == 1 and s.diagnosis["GENERATION_FAILURE"] == 1
    assert s.retrieval["recall_at_10"] == 0.5  # averaged over the 2 answerable questions only
    fa = s.failure_analysis
    assert fa["n_evaluated"] == 2 and fa["n_unanswerable"] == 2 and fa["unanswerable_correctly_abstained"] == 1


def test_financebench_dataset_loads_in_runner():
    d = load_dataset("finance_benchmark/datasets/finance_benchmark_v1.jsonl")
    assert len(d.samples) >= 100
    assert all(s.evidence for s in d.samples if s.answerable)
    assert all(not s.evidence for s in d.samples if not s.answerable)
    first = json.loads(open("finance_benchmark/datasets/finance_benchmark_v1.jsonl").readline())
    assert first["id"] == d.samples[0].id
