"""Teacher decisions, immutable AI scores, and audited final-score calculation."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.auth import owned_classroom
from core.config import AppError
from core.db import Assignment, AuditLog, CriterionResult, QuestionResult, Submission, User
from core.schemas import QuestionJudgement, Rubric, Transcript
from core.scoring import ExamScore, round_question, score_exam, score_question


def teacher_submission(session: Session, teacher: User, submission_id: int) -> tuple[Submission, Assignment]:
    """Authorize a final submission through classroom ownership."""
    submission = session.get(Submission, submission_id)
    assignment = session.get(Assignment, submission.assignment_id) if submission else None
    if not assignment:
        raise AppError("Submission not found.")
    owned_classroom(session, assignment.classroom_id, teacher)
    if submission.mode != "final" or submission.status not in {"graded", "approved", "rejected"}:
        raise AppError("Only processed final submissions can be reviewed.")
    return submission, assignment


def exam_result(session: Session, submission: Submission, assignment: Assignment, teacher: bool = False) -> ExamScore:
    """Compute totals through the pure engine, including optional and MCQ rules."""
    rubric = Rubric.model_validate(assignment.rubric_json)
    rows = list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == submission.id)))
    if {r.question_no for r in rows} != {q.id for q in rubric.questions}:
        raise AppError("Question results are incomplete. Process this submission again.")
    attempted = [a.question_id for a in Transcript.model_validate(submission.transcript_json).answers if a.text.strip()]
    wrong = set()
    for q in rubric.questions:
        decisions = list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == submission.id,
                                                                      CriterionResult.question_no == q.id)))
        if q.type == "mcq" and decisions and all(c.level == 0 for c in decisions):
            wrong.add(q.id)
    overrides = {r.question_no: r.teacher_score for r in rows if teacher and r.teacher_score is not None}
    return score_exam(rubric, {r.question_no:r.ai_score for r in rows}, attempted, wrong, overrides)


def change_question(session: Session, teacher: User, submission_id: int, question_id: str,
                    reason: str, score: float | None = None, levels: dict[str, float] | None = None) -> None:
    """Audit a teacher override; changing an approved result returns it to review."""
    submission, assignment = teacher_submission(session, teacher, submission_id)
    if not reason.strip():
        raise AppError("Explain the reason for this change.")
    rubric = Rubric.model_validate(assignment.rubric_json)
    question = next((q for q in rubric.questions if q.id == question_id), None)
    row = session.scalar(select(QuestionResult).where(QuestionResult.submission_id == submission_id,
                                                     QuestionResult.question_no == question_id))
    if not question or not row:
        raise AppError("Question result not found.")
    criteria = list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == submission_id,
                                                                 CriterionResult.question_no == question_id)))
    old = {"question":question_id, "score":row.teacher_score, "levels":{c.criterion_id:c.teacher_level for c in criteria},
           "status":submission.status, "reason":row.teacher_remark}
    if levels is not None:
        if set(levels) != {c.id for c in question.criteria} or any(v not in (0, 0.5, 1) for v in levels.values()):
            raise AppError("Provide one valid level for each criterion.")
        judgement = QuestionJudgement(question_id=question_id, criteria=[{"criterion_id":c.criterion_id,
            "level":c.level,"remark":c.remark,"evidence_quote":c.evidence_quote,"source_chunk_id":c.source_chunk_id,
            "confidence":c.confidence} for c in criteria], misconception=None, revision_tip="Teacher review")
        score = score_question(question, judgement, rubric.rules.round_to, levels=levels).score
        for criterion in criteria:
            criterion.teacher_level = levels[criterion.criterion_id]
    else:
        # A score override supersedes any older criterion-level override.
        for criterion in criteria:
            criterion.teacher_level = None
    if score is None or not 0 <= score <= question.max:
        raise AppError("Enter a score between zero and the question maximum.")
    row.teacher_score = round_question(score, question.max, rubric.rules.round_to)
    row.teacher_remark = reason.strip()
    submission.status = "graded"
    submission.final_total = None
    submission.final_percentage = None
    session.add(AuditLog(submission_id=submission_id, actor_id=teacher.id, action="teacher_edit", old_value=old,
        new_value={"question":question_id,"score":row.teacher_score,"levels":{c.criterion_id:c.teacher_level for c in criteria},
                   "reason":reason.strip(),"status":"graded"}))


def approve(session: Session, teacher: User, submission_id: int) -> ExamScore:
    """Recompute and release final marks only after an explicit teacher approval."""
    submission, assignment = teacher_submission(session, teacher, submission_id)
    # Preserve null for unedited questions so MCQ penalties still apply.
    result = exam_result(session, submission, assignment, teacher=True)
    old = {"status":submission.status,"total":submission.final_total,"percentage":submission.final_percentage}
    submission.final_total, submission.final_percentage = result.total, result.percentage
    submission.status = "approved"
    session.add(AuditLog(submission_id=submission_id, actor_id=teacher.id, action="approve", old_value=old,
        new_value={"status":"approved","total":result.total,"percentage":result.percentage,
                   "questions":result.questions,"counted":list(result.counted_questions),"penalty":result.penalty}))
    return result


def reject(session: Session, teacher: User, submission_id: int, comment: str) -> None:
    """Send a final attempt back with a mandatory comment, removing score release."""
    submission, _ = teacher_submission(session, teacher, submission_id)
    if not comment.strip():
        raise AppError("Add a comment explaining what the student should revise.")
    old = {"status":submission.status,"total":submission.final_total,"comment":submission.review_comment}
    submission.status = "rejected"
    submission.review_comment = comment.strip()
    submission.final_total = submission.final_percentage = None
    session.add(AuditLog(submission_id=submission_id, actor_id=teacher.id, action="reject", old_value=old,
                        new_value={"status":"rejected","comment":comment.strip()}))
