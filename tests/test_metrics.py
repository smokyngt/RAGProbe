import math

from rag_bench import metrics as M
from rag_bench.runner import diagnose

R = ["c21", "c84", "c93"]


def test_recall_hit_mrr():
    assert M.recall_at_k(R, ["c84"], 1) == 0.0
    assert M.recall_at_k(R, ["c84"], 3) == 1.0
    assert M.recall_at_k(R, ["c84", "zzz"], 3) == 0.5
    assert M.hit_at_k(R, ["c84", "zzz"], 3) == 1.0
    assert M.reciprocal_rank(R, ["c84"]) == 0.5
    assert M.reciprocal_rank(R, ["zzz"]) == 0.0


def test_ndcg():
    assert M.ndcg_at_k(["a", "b"], ["a"], 2) == 1.0
    assert math.isclose(M.ndcg_at_k(["b", "a"], ["a"], 2), 1 / math.log2(3))


def test_em_f1_normalisation():
    assert M.exact_match("Le contrat est conclu pour cinq ans.", "Contrat est conclu pour cinq ans !")
    assert M.exact_match("Le contrat a une durée de cinq ans.", "Le contrat est conclu pour cinq ans.") == 0.0
    assert 0 < M.f1_score("Le contrat a une durée de cinq ans.", "Le contrat est conclu pour cinq ans.") < 1
    assert M.f1_score("", "x") == 0.0


def test_diagnose():
    assert diagnose(R, ["c84"], True) == "ok"
    assert diagnose(R, ["zzz"], False) == "retrieval_miss"
    assert diagnose(R, ["c84"], False) == "ranking_or_context"
    assert diagnose(R, ["c21"], False) == "generation_error"
