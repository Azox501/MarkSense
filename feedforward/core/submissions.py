"""Submission persistence and student transcript confirmation."""
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from core.auth import enrolled_assignment
from core.config import AppError, get_settings
from core.db import AuditLog, Submission, User, session_scope
from core.ingest import read_pdf
from core.schemas import Rubric, Transcript


def create_submission(student: User, assignment_id: int, mode: str, data: bytes) -> int:
    """Validate membership and PDF, then store an immutable uploaded file."""
    if mode not in {"draft", "final"}:
        raise AppError("Choose Draft or Final.")
    with session_scope() as session:
        assignment = enrolled_assignment(session, assignment_id, student)
        if assignment.due_date and datetime.now() > assignment.due_date:
            raise AppError("The due date has passed. Ask your teacher how to submit a late attempt.")
        with read_pdf(data):
            pass
        folder = get_settings(False).data_dir / "uploads" / str(assignment.classroom_id) / str(assignment_id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{student.id}_{uuid.uuid4().hex}.pdf"
        path.write_bytes(data)
        submission = Submission(assignment_id=assignment_id, student_id=student.id, mode=mode,
                                file_path=str(path), status="uploaded")
        session.add(submission)
        session.flush()
        return submission.id


def student_submission(session: Session, submission_id: int, student: User) -> Submission:
    """Check ownership and classroom membership on every student write."""
    submission = session.get(Submission, submission_id)
    if not submission or submission.student_id != student.id:
        raise AppError("This submission is not available to your account.")
    enrolled_assignment(session, submission.assignment_id, student)
    return submission


def save_transcript(student: User, submission_id: int, transcript: Transcript, edited: bool = False) -> None:
    """Save OCR or a student correction before grading; retain corrections in the audit log."""
    with session_scope() as session:
        submission = student_submission(session, submission_id, student)
        if submission.status not in {"uploaded", "transcribed"}:
            raise AppError("Graded submissions cannot be changed. Upload a new attempt.")
        assignment = enrolled_assignment(session, submission.assignment_id, student)
        valid_ids = {q.id for q in Rubric.model_validate(assignment.rubric_json).questions}
        unknown = {a.question_id for a in transcript.answers} - valid_ids
        if unknown and edited:
            raise AppError("Unknown question IDs in transcript: " + ", ".join(sorted(unknown)))
        old = submission.transcript_json
        submission.transcript_json = transcript.model_dump()
        submission.status = "transcribed"
        if edited:
            session.add(AuditLog(submission_id=submission.id, actor_id=student.id, action="transcript_edit",
                                old_value=old, new_value=submission.transcript_json))
