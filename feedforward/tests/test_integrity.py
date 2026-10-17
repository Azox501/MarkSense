from core.integrity import compare_peers, cosine, lexical_similarity

TEXT = "Force is the product of mass and acceleration. Its SI unit is the newton."


def encoder(texts):
    return [[1.0, 0.0] if "Force" in text or "force" in text or "newton" in text else [0.0, 1.0] for text in texts]


def test_duplicate_and_unrelated():
    matches = compare_peers(TEXT, [(1, TEXT + " Extra."), (2, "Plants use sunlight to produce sugars during photosynthesis.")], 0.6, encoder)
    assert [m.submission_id for m in matches] == [1]
    assert matches[0].passages
    assert set(matches[0].passages[0]) == {"student", "peer"}


def test_empty_and_zero_vectors():
    assert lexical_similarity("", "") == 0
    assert cosine([0, 0], [1, 0]) == 0
    assert compare_peers("", [(1, TEXT)], 0.6, encoder) == []
    assert lexical_similarity(TEXT, TEXT) == 1
