"""Teacher-owned, approved-only final-sheet exports."""
from io import BytesIO

import pandas as pd
from sqlalchemy import select

from core.auth import owned_classroom
from core.config import AppError
from core.db import Assignment, CriterionResult, QuestionResult, Submission, User, session_scope
from core.review import exam_result
from core.schemas import Rubric


def safe_cell(value: str) -> str:
    """Prevent uploaded text or names from becoming spreadsheet formulas."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def final_sheet(teacher: User, assignment_id: int, remarks: bool = True) -> pd.DataFrame:
    """Export the latest approved final attempt for each student, with both score versions."""
    with session_scope() as session:
        assignment = session.get(Assignment, assignment_id)
        if not assignment:
            raise AppError("Assignment not found.")
        owned_classroom(session, assignment.classroom_id, teacher)
        rubric = Rubric.model_validate(assignment.rubric_json)
        submissions = list(session.scalars(select(Submission).where(Submission.assignment_id == assignment_id,
            Submission.mode == "final", Submission.status == "approved").order_by(Submission.created_at.desc(), Submission.id.desc())))
        records, seen = [], set()
        for submission in submissions:
            if submission.student_id in seen:
                continue
            seen.add(submission.student_id)
            student = session.get(User, submission.student_id)
            ai = exam_result(session, submission, assignment)
            final = exam_result(session, submission, assignment, teacher=True)
            rows = list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == submission.id)))
            by_q = {r.question_no:r for r in rows}
            record = {"Student":safe_cell(student.name),"Email":safe_cell(student.email),"Submission":submission.id}
            for q in rubric.questions:
                record[q.id + " AI"] = ai.questions[q.id]
                record[q.id + " Teacher"] = final.questions[q.id]
                record[q.id + " Counted"] = q.id in final.counted_questions
            record.update({"AI total":ai.total,"Teacher total":final.total,"Maximum":rubric.exam_max,
                           "Percentage":final.percentage,"MCQ penalty":final.penalty,"Status":"approved"})
            if remarks:
                criteria = list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == submission.id)))
                record["Criterion reasons"] = safe_cell(" | ".join(f"{c.criterion_id}: {c.remark}" for c in criteria))
                record["Teacher remarks"] = safe_cell(" | ".join(f"{r.question_no}: {r.teacher_remark}" for r in rows if r.teacher_remark))
            records.append(record)
    columns = ["Student", "Email", "Submission"]
    for q in rubric.questions:
        columns += [q.id + " AI", q.id + " Teacher", q.id + " Counted"]
    columns += ["AI total","Teacher total","Maximum","Percentage","MCQ penalty","Status"]
    if remarks:
        columns += ["Criterion reasons","Teacher remarks"]
    return pd.DataFrame(records, columns=columns)


def export_bytes(frame: pd.DataFrame, format: str) -> bytes:
    """Produce UTF-8 CSV or XLSX bytes for a Streamlit download button."""
    if format == "csv":
        return frame.to_csv(index=False).encode("utf-8-sig")
    if format != "xlsx":
        raise AppError("Choose CSV or XLSX.")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Approved results", index=False)
        sheet = writer.sheets["Approved results"]
        sheet.freeze_panes = "D2"
        sheet.auto_filter.ref = sheet.dimensions
        for cells in sheet.columns:
            sheet.column_dimensions[cells[0].column_letter].width = min(60, max(14, len(str(cells[0].value)) + 2))
    return buffer.getvalue()
