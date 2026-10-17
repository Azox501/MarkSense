"""Teacher classroom, resources and assignment setup."""
from sqlalchemy import select
import streamlit as st

from core.auth import add_student, create_classroom, owned_classroom
from core.db import Assignment, Classroom, Resource, session_scope
from core.ingest import ingest_resource
from core.schemas import Rubric
from core.ui import empty_state, friendly_errors, guard, page_header

st.set_page_config(page_title="MarkSense | Teacher setup", layout="wide")
teacher = guard("teacher")
page_header("Classrooms & assignments", "Bring your teaching materials, students, and simple question-by-question marking together.", "TEACHER WORKSPACE")
with session_scope() as session:
    has_classrooms = session.scalar(select(Classroom.id).where(Classroom.teacher_id == teacher.id)) is not None
with st.expander("Create a classroom", expanded=not has_classrooms):
    with st.form("classroom"):
        name = st.text_input("New classroom name")
        if st.form_submit_button("Create classroom"):
            with friendly_errors(), session_scope() as session:
                classroom = create_classroom(session, teacher, name)
                st.success(f"Created {classroom.name}. Join code: {classroom.join_code}")
with session_scope() as session:
    classrooms = list(session.scalars(select(Classroom).where(Classroom.teacher_id == teacher.id)))
if not classrooms:
    empty_state("Make room for learning", "Create your first classroom above. Then invite students and add your resources.")
    st.stop()
classroom = st.selectbox("Classroom", classrooms, format_func=lambda c: c.name)
settings_tab, materials_tab, assignments_tab = st.tabs(["Classroom settings", "Teaching materials", "Assignments"])
with settings_tab:
    st.code(classroom.join_code, language=None)
    with st.form("enroll"):
        email = st.text_input("Add a registered student by email")
        if st.form_submit_button("Enroll student"):
            with friendly_errors(), session_scope() as session:
                add_student(session, teacher, classroom.id, email)
                st.success("Student enrolled.")
    with st.form("threshold"):
        threshold = st.slider("Peer similarity threshold", 0.0, 1.0, float(classroom.similarity_threshold), 0.05)
        if st.form_submit_button("Save threshold"):
            with friendly_errors(), session_scope() as session:
                owned_classroom(session, classroom.id, teacher).similarity_threshold = threshold
                st.success("Threshold saved.")
with materials_tab:
    st.subheader("Teaching resources")
    kind = st.selectbox("Resource kind", ["notes", "answer_key", "question_paper"])
    upload = st.file_uploader("Upload a teacher PDF", type=["pdf"])
    if st.button("Index resource", disabled=upload is None):
        with friendly_errors():
            bar = st.progress(0.0)
            ingest_resource(teacher, classroom.id, kind, upload.name, upload.getvalue(), bar.progress)
            st.success("Resource indexed (identical uploads are reused).")
    with session_scope() as session:
        resources = list(session.scalars(select(Resource).where(Resource.classroom_id == classroom.id)))
    for resource in resources:
        st.caption(f"{resource.kind}: {resource.filename}")

with assignments_tab:
    st.subheader("Create an assignment")
    st.caption("Add each question, its type, the expected answer, and its marks. MarkSense handles the marking setup for you.")
    title = st.text_input("Assignment title")
    count = st.number_input("Number of questions", min_value=1, max_value=30, value=3, step=1)
    questions = []
    for i in range(1, int(count) + 1):
        with st.expander(f"Question {i}", expanded=i == 1):
            q_text = st.text_area("Question", key=f"text_{i}")
            q_type = st.selectbox("Type", ["descriptive", "mcq"], key=f"type_{i}")
            answer_label = "Correct option or answer" if q_type == "mcq" else "Expected answer"
            expected_answer = st.text_area(answer_label, key=f"answer_{i}")
            q_max = st.number_input("Marks", min_value=0.5, value=5.0, step=0.5, key=f"max_{i}")
            # Grading still uses one internal decision per question, but teachers never
            # have to define criteria or distribute marks across them.
            questions.append({
                "id": f"Q{i}", "text": q_text, "answer": expected_answer, "max": q_max,
                "type": q_type, "criteria": [{"id": f"Q{i}.answer", "name": "Answer quality",
                "max": q_max, "description": expected_answer or "Evaluate the answer to this question."}],
            })
    penalty = st.number_input("Penalty per wrong MCQ", min_value=0.0, value=0.25, step=0.25,
                              help="Set this to 0 when there is no negative marking.")
    raw = {"exam_max": sum(question["max"] for question in questions), "questions": questions,
           "rules": {"negative_marking": {"enabled": penalty > 0, "per_wrong": penalty, "applies_to": "mcq"},
                     "round_to": 0.01}}
    rubric = Rubric.model_validate(raw)
    complete = all(question["text"].strip() and question["answer"].strip() for question in questions)
    if not complete:
        st.caption("Add a question and its expected answer for every entry to create the assignment.")
    if st.button("Create assignment", disabled=not title.strip() or not complete):
        with friendly_errors(), session_scope() as session:
            owned_classroom(session, classroom.id, teacher)
            session.add(Assignment(classroom_id=classroom.id, title=title.strip(), kind="assignment",
                        rubric_json=rubric.model_dump(), max_marks=rubric.exam_max))
            st.success("Assignment created.")
    with session_scope() as session:
        assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id == classroom.id)))
    for assignment in assignments:
        st.caption(f"{assignment.title} · {assignment.kind} · maximum {assignment.max_marks:g}")
