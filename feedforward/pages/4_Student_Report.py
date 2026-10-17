"""Private draft history and teacher-approved diagnostic reports."""
from sqlalchemy import select
import streamlit as st

from core.db import Assignment, Submission, session_scope
from core.reports import student_report
from core.ui import empty_state, friendly_errors, guard, page_header

st.set_page_config(page_title="MarkSense | My reports", layout="wide")
student = guard("student")
page_header("Feedback to move you forward.", "Find your draft hints, teacher-approved results, and a clear plan for what to revise next.", "STUDENT WORKSPACE")
with session_scope() as session:
    attempts = list(session.scalars(select(Submission).where(Submission.student_id == student.id)
                                    .order_by(Submission.created_at.desc(), Submission.id.desc())))
    titles = {a.id:a.title for a in session.scalars(select(Assignment))}
if not attempts:
    empty_state("Your progress belongs here", "Submit a draft for guidance, or a final attempt for your teacher to review.")
    st.stop()
for attempt in attempts:
    with st.expander(f"{titles[attempt.assignment_id]} · {attempt.mode} · #{attempt.id} · {attempt.status}", expanded=attempt == attempts[0]):
        with friendly_errors():
            report = student_report(student, attempt.id)
            if report["mode"] == "draft":
                hints = report["hints"]
                if not hints:
                    st.info("Finish checking and processing your transcript to receive hints.")
                for hint in hints:
                    st.markdown("**" + hint["question_id"] + "**")
                    for text in hint["hints"]:
                        st.write("• " + text)
                    if hint["concepts_to_revise"]:
                        st.caption("Revise: " + ", ".join(hint["concepts_to_revise"]))
            elif report["status"] != "approved":
                if report["status"] == "rejected":
                    st.warning("Your teacher sent this attempt back. Revise and upload a new attempt.")
                    st.write(report["comment"])
                else:
                    st.info("Scores are released after teacher approval.")
            else:
                st.metric("Teacher-approved result", f"{report['total']:g} / {report['maximum']:g}", f"{report['percentage']:g}%", delta_color="off")
                if report["penalty"]:
                    st.caption(f"MCQ group penalty applied: {report['penalty']:g}")
                for question in report["questions"]:
                    st.markdown(f"**{question['question']} — {question['score']:g}/{question['maximum']:g}**" +
                        (" (not counted in the optional selection)" if not question["counted"] else ""))
                    for criterion in question["reasons"]:
                        st.write(f"{criterion['name']}: {criterion['reason']}")
                        if criterion["student_quote"]:
                            st.caption("Your answer: " + criterion["student_quote"])
                    if question["teacher_remark"]:
                        st.write("Teacher: " + question["teacher_remark"])
                    if question["misconception"]:
                        st.write("Concept to revisit: " + question["misconception"])
                st.markdown("**Revision plan**")
                for question in report["questions"]:
                    st.write(question["question"] + ": " + question["revision_tip"])
