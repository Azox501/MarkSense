import pytest

from core.schemas import QuestionJudgement, Rubric
from core.scoring import round_question, score_exam, score_question


def rubric_fixture():
    return Rubric.model_validate({"exam_max": 20, "questions": [
        {"id":"Q1","max":5,"criteria":[{"id":"Q1.c1","name":"Definition","max":3,"description":"Definition"},{"id":"Q1.c2","name":"Formula","max":2,"description":"Formula"}]},
        {"id":"Q2","max":5,"criteria":[{"id":"Q2.c1","name":"Method","max":3,"description":"Method"},{"id":"Q2.c2","name":"Result","max":2,"description":"Result"}]},
        {"id":"Q3","max":10,"criteria":[{"id":"Q3.c1","name":"Method","max":6,"description":"Method"},{"id":"Q3.c2","name":"Result","max":4,"description":"Result"}]}]})


def judgement(q, levels, confidence=0.9):
    return QuestionJudgement(question_id=q.id, criteria=[{"criterion_id":c.id,"level":level,"remark":"Reason",
        "evidence_quote":"quote","source_chunk_id":"chunk","confidence":confidence} for c, level in zip(q.criteria,levels)],
        misconception=None, revision_tip="Revise notes")


def test_worked_example():
    rubric = rubric_fixture()
    scores = {q.id:score_question(q, judgement(q, levels)).score for q, levels in
              zip(rubric.questions, [(1,0.5),(0.5,1),(1,0)])}
    assert scores == {"Q1":4,"Q2":3.5,"Q3":6}
    result = score_exam(rubric, scores, list(scores))
    assert result.total == 13.5
    assert result.percentage == 67.5


def test_rounding_cap_and_confidence():
    q = rubric_fixture().questions[0]
    q.max = 2.2
    assert score_question(q, judgement(q,[1,1],0.69)).score == 2
    assert round_question(5,2.3,0.5) == 2.3
    assert score_question(q, judgement(q,[1,1],0.69)).needs_review
    assert not score_question(q, judgement(q,[1,1],0.7)).needs_review
    assert round_question(1.25,5,0.5) == 1.5
    assert round_question(1.24,5,0.5) == 1


def test_optional_best_and_first():
    raw = rubric_fixture().model_dump()
    for q in raw["questions"]:
        q["optional_group"] = "G1"
        q["max"] = 10
    raw["exam_max"] = 20
    raw["rules"]["optional_groups"] = {"G1":{"attempt":2,"pick":"best"}}
    rubric = Rubric.model_validate(raw)
    scores = {"Q1":2,"Q2":5,"Q3":9}
    assert score_exam(rubric, scores, ["Q3","Q1","Q2"]).total == 14
    rubric.rules.optional_groups["G1"].pick = "first"
    assert score_exam(rubric, scores, ["Q3","Q1","Q2"]).total == 11


def test_mcq_negative_floor_and_teacher_override():
    rubric = rubric_fixture()
    for q in rubric.questions[:2]:
        q.type = "mcq"
    rubric.rules.negative_marking.enabled = True
    rubric.rules.negative_marking.per_wrong = 0.25
    result = score_exam(rubric, {"Q1":1,"Q2":0,"Q3":2}, ["Q1","Q2","Q3"], {"Q2","Q3"})
    assert result.total == 2.75  # descriptive Q3 is never penalized
    assert score_exam(rubric, {"Q1":0,"Q2":0,"Q3":2}, ["Q1","Q2","Q3"], {"Q1","Q2"}).total == 2
    assert score_exam(rubric, {"Q1":0,"Q2":0,"Q3":2}, ["Q1","Q2","Q3"], {"Q1","Q2"}, {"Q1":3}).total == 4.75


def test_missing_criterion_rejected():
    q = rubric_fixture().questions[0]
    bad = judgement(q,[1])
    with pytest.raises(ValueError):
        score_question(q,bad)
