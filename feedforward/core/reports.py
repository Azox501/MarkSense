"""Student-facing projections with a strict approval gate for final scores."""
from typing import Any

from sqlalchemy import select

from core.db import CriterionResult, QuestionResult, User, session_scope
from core.review import exam_result
from core.schemas import Rubric
from core.submissions import student_submission


def student_report(student: User, submission_id: int) -> dict[str, Any]:
    """Return hints or approved feedback; never expose unapproved numeric results."""
    from core.db import Assignment
    with session_scope() as session:
        submission = student_submission(session, submission_id, student)
        report: dict[str, Any] = {"id":submission.id,"mode":submission.mode,"status":submission.status,
                                  "comment":submission.review_comment}
        if submission.mode == "draft":
            report["hints"] = submission.hints_json or []
            return report
        if submission.status != "approved":
            return report
        assignment = session.get(Assignment, submission.assignment_id)
        rubric = Rubric.model_validate(assignment.rubric_json)
        final = exam_result(session, submission, assignment, teacher=True)
        rows = list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == submission.id)))
        criteria = list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == submission.id)))
        feedback = submission.feedback_json or {}
        questions = []
        for question in rubric.questions:
            row = next(r for r in rows if r.question_no == question.id)
            judgement = feedback.get(question.id, {}).get("judgement", {})
            reasons = [{"criterion":c.criterion_id,"name":next(x.name for x in question.criteria if x.id == c.criterion_id),
                "level":c.teacher_level if c.teacher_level is not None else c.level,"reason":c.remark,
                "student_quote":c.evidence_quote} for c in criteria if c.question_no == question.id]
            questions.append({"question":question.id,"score":final.questions[question.id],"maximum":question.max,
                "counted":question.id in final.counted_questions,"reasons":reasons,"teacher_remark":row.teacher_remark,
                "misconception":judgement.get("misconception"),"revision_tip":judgement.get("revision_tip", "Review your notes.")})
        report.update({"total":final.total,"maximum":rubric.exam_max,"percentage":final.percentage,
                       "penalty":final.penalty,"questions":questions})
        return report
