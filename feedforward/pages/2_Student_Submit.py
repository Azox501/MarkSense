"""Student enrollment, upload, transcript correction and grading requests."""
from pathlib import Path

from sqlalchemy import select
import streamlit as st

from core.auth import join_classroom
from core.db import Assignment, Enrollment, Submission, session_scope
from core.schemas import Rubric, Transcript, TranscribedAnswer
from core.submissions import create_submission, save_transcript, student_submission
from core.transcribe import transcribe_pdf
from core.ui import empty_state, friendly_errors, guard, page_header

st.set_page_config(page_title="MarkSense | Submit work", layout="wide")
student = guard("student")
page_header("Your next great attempt.", "Join your classroom, check your work, and submit when you're ready.", "STUDENT WORKSPACE")
with st.form("join"):
    code = st.text_input("Classroom join code")
    if st.form_submit_button("Join classroom"):
        with friendly_errors(), session_scope() as session:
            classroom = join_classroom(session, student, code)
            st.success(f"Joined {classroom.name}.")
with session_scope() as session:
    assignments = list(session.scalars(select(Assignment).join(Enrollment,
        Enrollment.classroom_id == Assignment.classroom_id).where(Enrollment.student_id == student.id)))
if not assignments:
    empty_state("Let's find your classroom", "Enter the six-character code your teacher shared. Your assignments will appear here.")
    st.stop()
assignment = st.selectbox("Assignment", assignments, format_func=lambda a: f"{a.title} (classroom {a.classroom_id})")
st.caption("Draft gives conceptual hints. Final goes to your teacher for review.")
mode = st.radio("Mode", ["draft", "final"], horizontal=True)
upload = st.file_uploader("Your answer PDF", type=["pdf"])
if st.button("Upload and transcribe", disabled=upload is None):
    with friendly_errors():
        submission_id = create_submission(student, assignment.id, mode, upload.getvalue())
        st.session_state["active_submission_id"] = submission_id
        bar = st.progress(0.0)
        transcript = transcribe_pdf(upload.getvalue(), bar.progress)
        save_transcript(student, submission_id, transcript)
        # The editable preview can remove unrecognized OCR question markers.
        st.session_state[f"ocr_{submission_id}"] = transcript.model_dump()
        st.success("Transcription ready. Check the preview before continuing.")
with session_scope() as session:
    pending = list(session.scalars(select(Submission).where(Submission.student_id == student.id,
        Submission.assignment_id == assignment.id, Submission.status.in_(["uploaded", "transcribed"]))
        .order_by(Submission.created_at.desc())))
if not pending:
    st.stop()
active = st.selectbox("Pending submission", pending,
    format_func=lambda s: f"#{s.id} · {s.mode} · {s.created_at:%d %b %H:%M}")
transcript_data = st.session_state.get(f"ocr_{active.id}", active.transcript_json)
if not transcript_data:
    st.info("This upload needs transcription. Retry after fixing your connection or API configuration.")
    if st.button("Retry transcription"):
        with friendly_errors():
            transcript = transcribe_pdf(Path(active.file_path).read_bytes(), st.progress(0.0).progress)
            save_transcript(student, active.id, transcript)
            st.session_state[f"ocr_{active.id}"] = transcript.model_dump()
            st.rerun()
    st.stop()
transcript = Transcript.model_validate(transcript_data)
rubric = Rubric.model_validate(assignment.rubric_json)
known = {a.question_id: a for a in transcript.answers}
unknown = set(known) - {q.id for q in rubric.questions}
if unknown:
    st.warning("OCR found extra question markers: " + ", ".join(sorted(unknown)) + ". Copy their text into the correct question below.")
    for qid in sorted(unknown):
        st.text_area(qid + " (unmatched OCR)", known[qid].text, disabled=True, key=f"unmatched_{active.id}_{qid}")
st.subheader("Correct transcription")
st.caption("Fix OCR mistakes only. Your teacher can compare this with the original PDF and the correction audit.")
answers = []
for question in rubric.questions:
    answer = known.get(question.id, TranscribedAnswer(question_id=question.id, text="", legibility=0))
    text = st.text_area(question.id, answer.text, key=f"answer_{active.id}_{question.id}")
    st.caption(f"OCR legibility: {answer.legibility:.0%}")
    answers.append(TranscribedAnswer(question_id=question.id, text=text, legibility=answer.legibility))
confirmed = st.checkbox("I checked the transcript against my uploaded PDF.", key=f"confirmed_{active.id}")
if st.button("Get draft hints" if active.mode == "draft" else "Send final for grading", disabled=not confirmed):
    with friendly_errors():
        save_transcript(student, active.id, Transcript(answers=answers), edited=True)
        from core.pipeline import process_submission
        bar = st.progress(0.0)
        warning = process_submission(student, active.id, bar.progress)
        if warning:
            st.warning(warning)
        st.success("Draft hints are ready in My reports." if active.mode == "draft" else "Grading complete. Your teacher will review before scores are released.")
        st.page_link("pages/4_Student_Report.py", label="Open my reports")
