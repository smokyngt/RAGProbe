import pytest

from ragbench.evaluation.judge import JudgeError, LLMJudge, build_prompt, parse_scores

GOOD = '{"correctness": 1.0, "completeness": 0.8, "groundedness": 1, "reason": "ok"}'


class Scripted:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, prompt):
        self.calls += 1
        return self.replies.pop(0)


def judge(*replies, attempts=2):
    c = Scripted(*replies)
    return LLMJudge(c, max_attempts=attempts), c


def ev(j):
    return j.evaluate("q", "ref", "ans", ["evidence"])


def test_parse_plain_fenced_and_chatty():
    assert parse_scores(GOOD).completeness == 0.8
    assert parse_scores(f"```json\n{GOOD}\n```").correctness == 1.0
    assert parse_scores(f"Voici : {GOOD} Fin.").groundedness == 1.0


def test_valid_json_single_call():
    j, c = judge(GOOD)
    assert ev(j).reason == "ok" and c.calls == 1


def test_retry_after_invalid_then_ok():
    j, c = judge("pas du json", GOOD)
    assert ev(j).correctness == 1.0 and c.calls == 2


def test_out_of_range_score_is_rejected():
    j, _ = judge('{"correctness": 1.7, "completeness": 1, "groundedness": 1}',
                 '{"correctness": 1, "completeness": 1}')  # dimension manquante
    with pytest.raises(JudgeError):
        ev(j)


def test_prompt_contains_all_inputs_and_handles_empty_evidence():
    p = build_prompt("Q?", "REF", "ANS", ["passage un", "passage deux"])
    assert all(x in p for x in ("Q?", "REF", "ANS", "[1] passage un", "[2] passage deux"))
    assert "no evidence retrieved" in build_prompt("Q?", "REF", "ANS", [])
