"""Key facts (deterministic scoring) and the natural question variant."""
from ragbench.config import BenchmarkConfig, Config, PipelineConfig
from ragbench.dataset import Dataset
from ragbench.evaluation.qa import fact_normalize, fact_present, key_fact_scores
from ragbench.models import EvidenceRef, KeyFact, PipelineResult, RetrievedChunk, Sample
from ragbench.pipelines import PipelineAdapter
from ragbench.runner import BenchmarkRunner


def test_fact_normalisation():
    assert fact_normalize("€ 1,540 million") == "€1540 million"
    assert fact_normalize("29.4 %") == "29.4%"
    assert fact_normalize("−1 494") == "-1494"
    assert fact_normalize("CHF 1'234.5") == "chf 1234.5"


def test_fact_present_number_boundaries():
    assert fact_present("The rate was 29.4 % in 2025.", ["29.4%"])
    assert fact_present("EUR 1540m", ["1,540"])
    assert not fact_present("11,540", ["1,540"])  # never inside a longer number
    assert not fact_present("2.75 euros", ["2.7"])  # never a prefix of a longer decimal
    assert fact_present("about €1.54 billion", ["€1,540 million", "€1.54 billion"])


def test_key_fact_scores():
    kf = [KeyFact(fact="rate", value="29.4%"), KeyFact(fact="taxes", value="€1,540 million", accept=["€1.54 billion"])]
    assert key_fact_scores("29.4% on €1.54 billion of taxes", kf) == {"key_fact_recall": 1.0, "key_facts_all": 1.0}
    assert key_fact_scores("about 29%", kf) == {"key_fact_recall": 0.0, "key_facts_all": 0.0}


class Echo(PipelineAdapter):
    """Returns a scripted answer and records the question text it received."""
    name, version = "echo", "v0"

    def __init__(self, answer):
        self.answer, self.seen = answer, []

    def query(self, question):
        self.seen.append(question)
        return PipelineResult(answer=self.answer, latency_ms=1.0,
                              retrieved_chunks=[RetrievedChunk(chunk_id="c", document_id="fin_doc_011", page=162)])


def run(tmp_path, adapter, field="question"):
    s = Sample(id="q", question="What was DHL Group's consolidated effective income tax rate for fiscal year 2025?",
               question_natural="DHL tax rate 2025?", reference_answer="DHL Group's consolidated effective income tax rate for fiscal year 2025 was 29.4%.",
               key_facts=[KeyFact(fact="rate", value="29.4%")], evidence=[EvidenceRef(document_id="fin_doc_011", page=162)])
    cfg = Config(pipeline=PipelineConfig(name="e", endpoint="http://unused"), benchmark=BenchmarkConfig(question_field=field))
    (tmp_path / "r").mkdir()
    return BenchmarkRunner(cfg, adapter).run(Dataset("d", "v", tmp_path / "d", "h", [s]), "r", tmp_path / "r")


def test_key_facts_drive_correctness_without_judge(tmp_path):
    # short answer: low token F1 but every key fact present -> correct
    s = run(tmp_path, Echo("29.4%"))
    assert s.diagnosis["SUCCESS"] == 1 and s.qa["key_facts_all"] == 1.0 and s.qa["token_f1"] < 0.5


def test_natural_variant_is_sent(tmp_path):
    a = Echo("29.4%")
    run(tmp_path, a, field="question_natural")
    assert a.seen == ["DHL tax rate 2025?"]
