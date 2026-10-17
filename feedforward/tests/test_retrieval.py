from core.retrieval import rrf


def test_rrf_ordering():
    rankings = [["a", "b", "c"], ["b", "c", "d"]]
    result = rrf(rankings)
    assert [i for i, _ in result] == ["b", "c", "a", "d"]
    assert result[0][1] == 1 / 62 + 1 / 61


def test_rrf_duplicate_not_double_counted():
    assert rrf([["a", "a"]]) == [("a", 1 / 61)]
