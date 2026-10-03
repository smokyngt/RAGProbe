import pytest

from ragbench.config import Config, PipelineConfig
from ragbench.dataset import Dataset
from ragbench.models import FailureType, JudgeScores, PipelineResult, RetrievedChunk, Sample
from ragbench.pipelines import PipelineAdapter, PipelineError
from ragbench.reporting.aggregator import percentile
from ragbench.runner import BenchmarkRunner
from ragbench.storage import load_summary, load_traces


class Fake(PipelineAdapter):
    """Réponses scriptées par question : {question: (answer, [chunk_ids]) | Exception}."""
    name, version = "fake", "v0"

    def __init__(self, script):
        self.script = script

    def query(self, question):
        r = self.script[question]
        if isinstance(r, Exception):
            raise r
        return PipelineResult(answer=r[0], latency_ms=10.0,
                              retrieved_chunks=[RetrievedChunk(chunk_id=c, text=f"texte {c}") for c in r[1]])


def sample(i, ref="cinq ans", rel=("g",)):
    return Sample(id=f"q{i}", question=f"Q{i}", reference_answer=ref, relevant_chunks=list(rel))


def run(tmp_path, samples, script, judge=None):
    cfg = Config(pipeline=PipelineConfig(name="fake", endpoint="http://unused"))
    ds = Dataset("ds", "v1", tmp_path / "ds.jsonl", "abc", samples)
    (tmp_path / "run").mkdir()
    return BenchmarkRunner(cfg, Fake(script), judge).run(ds, "run", tmp_path / "run")


def test_four_cases_and_files(tmp_path):
    s = [sample(1), sample(2), sample(3), sample(4)]
    script = {
        "Q1": ("cinq ans", ["g", "x"]),          # preuves + bonne réponse            -> SUCCESS
        "Q2": ("dix mois", ["g", "x"]),          # preuves + mauvaise réponse         -> GENERATION_FAILURE
        "Q3": ("dix mois", ["x", "y"]),          # preuves absentes + mauvaise réponse -> RETRIEVAL_FAILURE
        "Q4": PipelineError("HTTP 500"),         # panne                              -> PIPELINE_ERROR
    }
    summary = run(tmp_path, s, script)
    assert summary.diagnosis == {"SUCCESS": 1, "GENERATION_FAILURE": 1, "RETRIEVAL_FAILURE": 1,
                                 "GROUNDING_FAILURE": 0, "PIPELINE_ERROR": 1}
    assert summary.n_errors == 1 and summary.n_questions == 4
    # erreurs comptées à zéro : recall@1 = 2 succès sur 4 questions (Q1, Q2)
    assert summary.retrieval["recall_at_1"] == 0.5
    fa = summary.failure_analysis
    assert (fa["retrieval_ok_answer_correct"], fa["retrieval_ok_answer_wrong"], fa["retrieval_missed_answer_wrong"]) == (1, 1, 1)
    assert fa["wrong_answers_due_to_retrieval"] == 0.5 and fa["wrong_answers_due_to_generation"] == 0.5
    # fichiers : une trace complète par question
    assert (tmp_path / "run" / "summary.json").exists()
    lines = (tmp_path / "run" / "traces.jsonl").read_text().splitlines()
    assert len(lines) == 4


def test_trace_contents_and_roundtrip(tmp_path):
    run(tmp_path, [sample(1)], {"Q1": ("cinq ans", ["x", "g"])})
    t = load_traces(tmp_path, "run")[0]
    assert t.question_id == "q1" and t.input.question == "Q1"
    assert t.ground_truth.relevant_chunks == ["g"] and t.pipeline_output.answer == "cinq ans"
    assert t.metrics["recall_at_1"] == 0.0 and t.metrics["recall_at_5"] == 1.0 and t.metrics["mrr"] == 0.5
    assert t.metrics["exact_match"] == 1.0 and t.latency_ms == 10.0
    assert t.analysis.retrieval_ok and t.analysis.answer_correct_source == "token_f1"
    assert load_summary(tmp_path, "run").run.dataset_sha256 == "abc"


class FixedJudge:
    name = "fixed"

    def __init__(self, scores=None, boom=False):
        self.scores, self.boom = scores, boom

    def evaluate(self, *a, **k):
        if self.boom:
            raise RuntimeError("judge down")
        return self.scores


def test_judge_drives_correctness_and_grounding(tmp_path):
    ungrounded = JudgeScores(correctness=1, completeness=1, groundedness=0.0, reason="invented")
    s = run(tmp_path, [sample(1)], {"Q1": ("cinq ans", ["g"])}, FixedJudge(ungrounded))
    assert s.diagnosis["GROUNDING_FAILURE"] == 1 and s.judge["groundedness"] == 0.0 and s.n_judged == 1


def test_judge_failure_is_recorded_not_fatal(tmp_path):
    s = run(tmp_path, [sample(1)], {"Q1": ("cinq ans", ["g"])}, FixedJudge(boom=True))
    t = load_traces(tmp_path, "run")[0]
    assert "judge down" in t.judge_error and t.judge is None and s.judge is None
    assert t.diagnosis == FailureType.SUCCESS  # repli sur token_f1


def test_percentile():
    assert percentile([], 50) == 0.0
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([0, 10], 95) == pytest.approx(9.5)
