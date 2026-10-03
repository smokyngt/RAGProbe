from ragbench.evaluation.qa import exact_match, normalize, token_f1


def test_normalize():
    assert normalize("  Le  Contrat, est CONCLU !  ") == "contrat est conclu"
    assert normalize("L'énergie « verte »") == "energie verte"
    assert "a" in normalize("Le contrat a une durée").split()  # "a" (verbe) n'est pas un article


def test_exact_match():
    assert exact_match("Le contrat est conclu pour cinq ans.", "contrat est conclu pour cinq ans") == 1.0
    assert exact_match("cinq ans", "dix ans") == 0.0


def test_token_f1():
    assert token_f1("cinq ans", "cinq ans") == 1.0
    assert token_f1("cinq ans", "dix ans") == 0.5  # P=R=1/2
    assert token_f1("", "cinq ans") == 0.0
    assert token_f1("", "") == 1.0
    assert token_f1("zéro", "cinq ans") == 0.0
