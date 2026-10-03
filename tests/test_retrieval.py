import math

import pytest

from ragbench.evaluation.retrieval import (evaluate_retrieval, ndcg_at_k, precision_at_k, recall_at_k,
                                           reciprocal_rank, validate_metric_names)

RETRIEVED = ["chunk_21", "chunk_84", "chunk_93"]


def test_spec_example():
    """Exemple de l'énoncé : vérité = chunk_84 en 2e position."""
    out = evaluate_retrieval(RETRIEVED, ["chunk_84"], ks=[1, 5, 10], metrics=["recall", "mrr"])
    assert out == {"recall_at_1": 0.0, "recall_at_5": 1.0, "recall_at_10": 1.0, "mrr": 0.5}


def test_recall_partial_with_several_relevant():
    rel = {"chunk_84", "chunk_93", "missing"}
    assert recall_at_k(RETRIEVED, rel, 1) == 0.0
    assert recall_at_k(RETRIEVED, rel, 3) == pytest.approx(2 / 3)


def test_recall_empty_relevant_and_k_larger_than_list():
    assert recall_at_k(RETRIEVED, set(), 5) == 0.0
    assert recall_at_k([], {"a"}, 5) == 0.0
    assert recall_at_k(["a"], {"a"}, 100) == 1.0


def test_mrr():
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0
    assert reciprocal_rank(["a", "b", "c"], {"c", "b"}) == 0.5  # premier pertinent = rang 2
    assert reciprocal_rank(["a"], {"z"}) == 0.0
    assert reciprocal_rank([], {"z"}) == 0.0


def test_precision_and_ndcg():
    assert precision_at_k(RETRIEVED, {"chunk_84"}, 2) == 0.5
    assert ndcg_at_k(["a", "b"], {"a"}, 2) == 1.0
    assert ndcg_at_k(["b", "a"], {"a"}, 2) == pytest.approx(1 / math.log2(3))
    assert ndcg_at_k(["x"], {"a"}, 5) == 0.0


def test_duplicates_count_once():
    # le même chunk retourné 3 fois ne doit pas pousser la vérité hors du top-K ni gonfler le rang
    out = evaluate_retrieval(["x", "x", "x", "gold"], ["gold"], ks=[2], metrics=["recall", "mrr"])
    assert out == {"recall_at_2": 1.0, "mrr": 0.5}


def test_metric_selection_and_validation():
    assert set(evaluate_retrieval(["a"], ["a"], [1], ["precision"])) == {"precision_at_1"}
    with pytest.raises(ValueError):
        validate_metric_names(["recall", "bogus"])
