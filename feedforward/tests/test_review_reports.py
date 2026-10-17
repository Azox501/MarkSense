import pytest
from sqlalchemy import select

from core.auth import create_classroom, join_classroom, register
from core.config import AppError
from core.db import Assignment, AuditLog, CriterionResult, QuestionResult, Submission, session_scope
from core.export import export_bytes, final_sheet
from core.reports import student_report
from core.review import approve, change_question, reject
from core.schemas import Transcript
from test_scoring import rubric_fixture


def seed_review():
    with session_scope() as session:
        teacher = register(session,"Teacher","teacher@demo.test","password123","teacher")
        student = register(session,"Student","student@demo.test","password123","student")
        other = register(session,"Other","other@demo.test","password123","student")
        classroom = create_classroom(session,teacher,"Class")
        join_classroom(session,student,classroom.join_code)
        join_classroom(session,other,classroom.join_code)
        rubric = rubric_fixture()
        assignment = Assignment(classroom_id=classroom.id,title="Test",kind="exam",rubric_json=rubric.model_dump(),max_marks=20)
        session.add(assignment)
        session.flush()
        transcript = Transcript.model_validate({"answers":[{"question_id":q.id,"text":"Answer","legibility":1} for q in rubric.questions]})
        submission = Submission(assignment_id=assignment.id,student_id=student.id,mode="final",file_path="dummy.pdf",
                                transcript_json=transcript.model_dump(),status="graded")
        session.add(submission)
        session.flush()
        for q,value in zip(rubric.questions,[4,3.5,6]):
            session.add(QuestionResult(submission_id=submission.id,question_no=q.id,ai_score=value,max_marks=q.max,needs_review=False))
            for c in q.criteria:
                session.add(CriterionResult(submission_id=submission.id,question_no=q.id,criterion_id=c.id,level=1,
                    ai_marks=c.max,remark="Reason",evidence_quote="Answer",source_chunk_id=None,confidence=0.9))
        return teacher,student,other,assignment.id,submission.id


def test_approval_export_edit_audit(local_db):
    teacher,student,other,assignment_id,sid = seed_review()
    assert "total" not in student_report(student,sid)
    assert final_sheet(teacher,assignment_id).empty
    with pytest.raises(AppError):
        student_report(other,sid)
    with session_scope() as session:
        assert approve(session,teacher,sid).total == 13.5
    assert student_report(student,sid)["total"] == 13.5
    frame = final_sheet(teacher,assignment_id)
    assert len(frame) == 1
    assert export_bytes(frame,"xlsx").startswith(b"PK")
    assert b"approved" in export_bytes(frame,"csv")
    with session_scope() as session:
        change_question(session,teacher,sid,"Q1","OCR correction",score=5)
    assert final_sheet(teacher,assignment_id).empty
    with session_scope() as session:
        assert approve(session,teacher,sid).total == 14.5
        result = session.scalar(select(QuestionResult).where(QuestionResult.submission_id == sid,QuestionResult.question_no == "Q1"))
        assert result.ai_score == 4
        log = session.scalar(select(AuditLog).where(AuditLog.action == "teacher_edit"))
        assert log.old_value["score"] is None and log.new_value["score"] == 5
    with session_scope() as session:
        reject(session,teacher,sid,"Please revise Q2")
    assert "total" not in student_report(student,sid)


def test_draft_projection_never_has_scores(local_db):
    teacher,student,_,_,sid = seed_review()
    with session_scope() as session:
        submission = session.get(Submission,sid)
        submission.mode = "draft"
        submission.hints_json = [{"question_id":"Q1","hints":["Which law connects force to motion?"],"concepts_to_revise":["Newton's laws"]}]
    report = student_report(student,sid)
    assert set(report) == {"id","mode","status","comment","hints"}
    assert report["hints"]
