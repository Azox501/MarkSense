"""Prioritized review, evidence inspection, audited edits and approved exports."""
from pathlib import Path

from sqlalchemy import select
import streamlit as st

from core.db import Assignment, AuditLog, Classroom, CriterionResult, IntegrityReport, QuestionResult, Submission, User, session_scope
from core.export import export_bytes, final_sheet
from core.review import approve, change_question, exam_result, reject, teacher_submission
from core.schemas import Rubric, Transcript
from core.ui import friendly_errors, guard

st.set_page_config(page_title="MarkSense | Teacher review", layout="wide")
teacher = guard("teacher")
st.title("Review and approve")
with session_scope() as session:
    assignments = list(session.scalars(select(Assignment).join(Classroom).where(Classroom.teacher_id == teacher.id)))
if not assignments:
    st.info("Create an assignment first.")
    st.stop()
assignment = st.selectbox("Assignment", assignments, format_func=lambda a: f"{a.title} (classroom {a.classroom_id})")
show_history = st.checkbox("Include approved and rejected attempts")
with session_scope() as session:
    candidates = list(session.scalars(select(Submission).where(Submission.assignment_id == assignment.id,
        Submission.mode == "final", Submission.status.in_(["graded","approved","rejected"] if show_history else ["graded"]))))
    student_names = {u.id:u.name for u in session.scalars(select(User).where(User.id.in_([s.student_id for s in candidates])))}
    flags = set(session.scalars(select(IntegrityReport.submission_id).where(IntegrityReport.submission_id.in_([s.id for s in candidates]))))
    low_confidence = set(session.scalars(select(QuestionResult.submission_id).where(
        QuestionResult.submission_id.in_([s.id for s in candidates]), QuestionResult.needs_review.is_(True))))
candidates.sort(key=lambda s: (s.id not in flags, s.id not in low_confidence, s.created_at, s.id))
if candidates:
    submission = st.selectbox("Review queue", candidates, format_func=lambda s:
        f"#{s.id} · {student_names[s.student_id]} · {s.status}" + (" · Peer similarity" if s.id in flags else "") +
        (" · Low confidence" if s.id in low_confidence else ""))
    rubric = Rubric.model_validate(assignment.rubric_json)
    with session_scope() as session:
        teacher_submission(session, teacher, submission.id)
        reports = list(session.scalars(select(IntegrityReport).where(IntegrityReport.submission_id == submission.id)))
        questions = list(session.scalars(select(QuestionResult).where(QuestionResult.submission_id == submission.id)))
        criteria = list(session.scalars(select(CriterionResult).where(CriterionResult.submission_id == submission.id)))
        edits = list(session.scalars(select(AuditLog).where(AuditLog.submission_id == submission.id).order_by(AuditLog.id)))
        preview = exam_result(session, submission, assignment, teacher=True)
    st.metric("Current review total", f"{preview.total:g} / {rubric.exam_max:g}")
    st.caption(f"Counted: {', '.join(preview.counted_questions)}. MCQ group penalty: {preview.penalty:g}.")
    if Path(submission.file_path).exists():
        st.download_button("Download original answer PDF", Path(submission.file_path).read_bytes(),
                           file_name=f"submission_{submission.id}.pdf", mime="application/pdf")
    for report in reports:
        with session_scope() as session:
            peer = session.get(Submission, report.matched_submission_id)
            peer_name = session.get(User, peer.student_id).name
        with st.expander(f"Peer similarity: {report.similarity:.0%} · {peer_name} (#{peer.id})", expanded=True):
            for passage in report.flagged_passages_json:
                a, b = st.columns(2)
                a.write(passage["student"])
                b.write(passage["peer"])
            st.caption("This is a similarity signal. The teacher decides how to respond.")
    transcript = {a.question_id:a for a in Transcript.model_validate(submission.transcript_json).answers}
    for question in rubric.questions:
        result = next(r for r in questions if r.question_no == question.id)
        details = (submission.feedback_json or {}).get(question.id, {})
        with st.expander(f"{question.id} · AI {result.ai_score:g}/{result.max_marks:g}" + (" · Needs review" if result.needs_review else ""), expanded=True):
            left, right = st.columns(2)
            with left:
                st.markdown("**Student answer**")
                st.write(transcript[question.id].text if question.id in transcript else "No answer")
                st.markdown("**Criterion decisions**")
                relevant = [c for c in criteria if c.question_no == question.id]
                for c in relevant:
                    st.write(f"{c.criterion_id}: level {c.level:g}; confidence {c.confidence:.0%}")
                    st.write(c.remark)
                    st.caption(f"Student quote: {c.evidence_quote or '(empty)'} · source: {c.source_chunk_id or 'unsupported'}")
                    if c.teacher_level is not None:
                        st.caption(f"Teacher level: {c.teacher_level:g}")
            with right:
                st.markdown("**Retrieved teacher evidence**")
                for evidence in details.get("evidence", []):
                    st.caption(f"{evidence['kind']} · page {evidence['page']} · {evidence['id']}")
                    st.write(evidence["text"])
                judgement = details.get("judgement", {})
                if judgement.get("misconception"):
                    st.write("Misconception: " + judgement["misconception"])
                st.write("Revision: " + judgement.get("revision_tip", "Review the notes."))
            with st.form(f"edit_{submission.id}_{question.id}"):
                edit_method = st.radio("Edit method", ["Question score", "Criterion levels"], key=f"method_{submission.id}_{question.id}")
                new_score = st.number_input("Teacher question score", min_value=0.0, max_value=float(question.max),
                    value=float(result.teacher_score if result.teacher_score is not None else result.ai_score),
                    step=float(rubric.rules.round_to), key=f"score_{submission.id}_{question.id}")
                new_levels = {}
                for c in relevant:
                    current_level = c.teacher_level if c.teacher_level is not None else c.level
                    new_levels[c.criterion_id] = st.selectbox(c.criterion_id + " teacher level", [0.0,0.5,1.0],
                        index=[0.0,0.5,1.0].index(current_level), key=f"level_{submission.id}_{c.id}")
                reason = st.text_area("Reason (required)", value=result.teacher_remark, key=f"reason_{submission.id}_{question.id}")
                if st.form_submit_button("Save edit"):
                    with friendly_errors():
                        with session_scope() as session:
                            change_question(session, teacher, submission.id, question.id, reason,
                                score=new_score if edit_method == "Question score" else None,
                                levels=new_levels if edit_method == "Criterion levels" else None)
                        st.rerun()
    approve_column, reject_column = st.columns(2)
    if approve_column.button("Approve and release scores", type="primary"):
        with friendly_errors():
            with session_scope() as session:
                approve(session, teacher, submission.id)
            st.rerun()
    rejection = reject_column.text_area("Send-back comment")
    if reject_column.button("Reject / send back"):
        with friendly_errors():
            with session_scope() as session:
                reject(session, teacher, submission.id, rejection)
            st.rerun()
    with st.expander("Audit history"):
        for entry in edits:
            st.caption(f"{entry.timestamp} · actor {entry.actor_id} · {entry.action}")
            st.json({"old":entry.old_value,"new":entry.new_value})
else:
    st.info("No submissions in this review queue.")
st.subheader("Final sheet")
remarks = st.checkbox("Include per-criterion reasons and teacher remarks", value=True)
with friendly_errors():
    frame = final_sheet(teacher, assignment.id, remarks)
    st.dataframe(frame, hide_index=True)
    st.caption("Latest approved final attempt per student. AI and teacher marks are separate.")
    if not frame.empty:
        st.download_button("Download CSV", export_bytes(frame,"csv"), file_name="approved_results.csv", mime="text/csv")
        st.download_button("Download XLSX", export_bytes(frame,"xlsx"), file_name="approved_results.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
