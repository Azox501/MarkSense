"""Submission orchestration with three question workers and atomic score writes."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import delete, select

from core.config import AppError, get_settings
from core.db import CriterionResult, QuestionResult, Submission, User, session_scope
from core.integrity import check_submission
from core.judge import draft_hints, judge_question
from core.retrieval import Evidence, retrieve
from core.schemas import DraftHint, Question, QuestionJudgement, Rubric, Transcript
from core.scoring import score_question
from core.submissions import student_submission


def process_submission(student: User, submission_id: int,
                       progress: Callable[[float], None] = lambda _: None) -> str | None:
    """Run peer checks and grading/hints after the student's transcript confirmation."""
    from core.db import Assignment
    with session_scope() as session:
        submission = student_submission(session, submission_id, student)
        if submission.status != "transcribed":
            raise AppError("Confirm a transcript before processing this submission.")
        assignment = session.get(Assignment, submission.assignment_id)
        rubric = Rubric.model_validate(assignment.rubric_json)
        transcript = Transcript.model_validate(submission.transcript_json)
        classroom_id, mode, assignment_id = assignment.classroom_id, submission.mode, assignment.id
    matches = check_submission(submission_id, classroom_id)
    answers = {a.question_id: a for a in transcript.answers}
    results = {}
    evidence_map = {}
    def process(question: Question) -> tuple[DraftHint | QuestionJudgement, list[Evidence]]:
        answer = answers.get(question.id)
        text = answer.text if answer else ""
        evidence = retrieve(classroom_id, question.id, question.text, text)
        decision = (draft_hints(question, text, evidence) if mode == "draft" else
                    judge_question(question, text, evidence, rubric.rules.carry_forward))
        if mode == "final" and (answer is None or answer.legibility < 0.5):
            for criterion in decision.criteria:
                criterion.confidence = min(criterion.confidence, 0.49)
        return decision, evidence
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(process, q): q.id for q in rubric.questions}
        for index, future in enumerate(as_completed(futures), 1):
            qid = futures[future]
            results[qid], evidence_map[qid] = future.result()
            progress(index / len(futures))
    warning = None
    with session_scope() as session:
        current = student_submission(session, submission_id, student)
        if current.status != "transcribed" or current.transcript_json != transcript.model_dump():
            raise AppError("This submission changed during processing. Please refresh.")
        session.execute(delete(CriterionResult).where(CriterionResult.submission_id == submission_id))
        session.execute(delete(QuestionResult).where(QuestionResult.submission_id == submission_id))
        if mode == "draft":
            current.hints_json = [results[q.id].model_dump() for q in rubric.questions]
            current.feedback_json = None
            previous_warning = session.scalar(select(Submission.id).where(Submission.student_id == student.id,
                Submission.assignment_id == assignment_id, Submission.similarity_warning_shown.is_(True)))
            if matches and previous_warning is None:
                current.similarity_warning_shown = True
                warning = "Peer similarity: some passages resemble another submission. Check that this draft reflects your own understanding."
        else:
            feedback = {}
            for question in rubric.questions:
                decision = results[question.id]
                score = score_question(question, decision, rubric.rules.round_to, get_settings(False).confidence_threshold)
                session.add(QuestionResult(submission_id=submission_id, question_no=question.id,
                    ai_score=score.score, max_marks=question.max, needs_review=score.needs_review))
                for criterion in decision.criteria:
                    session.add(CriterionResult(submission_id=submission_id, question_no=question.id,
                        criterion_id=criterion.criterion_id, level=criterion.level,
                        ai_marks=score.criterion_marks[criterion.criterion_id], remark=criterion.remark,
                        evidence_quote=criterion.evidence_quote, source_chunk_id=criterion.source_chunk_id,
                        confidence=criterion.confidence))
                feedback[question.id] = {"judgement": decision.model_dump(),
                                        "evidence": [d.as_dict() for d in evidence_map[question.id]]}
            current.feedback_json = feedback
            current.hints_json = None
        current.status = "graded"
    return warning
