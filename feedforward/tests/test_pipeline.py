from sqlalchemy import select

from core import pipeline
from core.db import CriterionResult, QuestionResult, Submission, session_scope
from core.schemas import DraftHint, QuestionJudgement
from test_review_reports import seed_review


def test_pipeline_draft_no_marks_final_atomic(local_db, monkeypatch):
    teacher,student,_,_,sid = seed_review()
    monkeypatch.setattr(pipeline,"check_submission",lambda *args: [])
    monkeypatch.setattr(pipeline,"retrieve",lambda *args: [])
    monkeypatch.setattr(pipeline,"draft_hints",lambda q,*args: DraftHint(question_id=q.id,
        hints=["Which idea from the notes applies here?"],concepts_to_revise=["Method"]))
    with session_scope() as session:
        row = session.get(Submission,sid)
        row.mode = "draft"
        row.status = "transcribed"
    pipeline.process_submission(student,sid)
    with session_scope() as session:
        row = session.get(Submission,sid)
        assert row.status == "graded" and row.hints_json
        assert not list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == sid)))
        assert not list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == sid)))
        row.mode = "final"
        row.status = "transcribed"
    def judge(q,*args):
        return QuestionJudgement(question_id=q.id,criteria=[{"criterion_id":c.id,"level":1,"remark":"Reason",
            "evidence_quote":"Answer","source_chunk_id":None,"confidence":0.4} for c in q.criteria],
            misconception=None,revision_tip="Revise notes")
    monkeypatch.setattr(pipeline,"judge_question",judge)
    pipeline.process_submission(student,sid)
    with session_scope() as session:
        row = session.get(Submission,sid)
        assert row.status == "graded" and row.hints_json is None
        assert row.final_total is None
        assert len(list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == sid)))) == 3


def test_pipeline_failure_does_not_store_partial_marks(local_db, monkeypatch):
    from sqlalchemy import delete
    teacher,student,_,_,sid = seed_review()
    with session_scope() as session:
        session.get(Submission,sid).status = "transcribed"
        session.execute(delete(QuestionResult).where(QuestionResult.submission_id == sid))
        session.execute(delete(CriterionResult).where(CriterionResult.submission_id == sid))
    monkeypatch.setattr(pipeline,"check_submission",lambda *args: [])
    monkeypatch.setattr(pipeline,"retrieve",lambda *args: [])
    def fail(*args):
        raise ValueError("upstream failed")
    monkeypatch.setattr(pipeline,"judge_question",fail)
    import pytest
    with pytest.raises(ValueError):
        pipeline.process_submission(student,sid)
    with session_scope() as session:
        assert session.get(Submission,sid).status == "transcribed"
        assert list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == sid))) == []
