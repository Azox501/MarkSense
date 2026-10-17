"""Teacher classroom, resources and rubric setup."""
import json
from datetime import datetime, time

from pydantic import ValidationError
from sqlalchemy import select
import streamlit as st

from core.auth import add_student, create_classroom, owned_classroom
from core.db import Assignment, Classroom, Resource, session_scope
from core.ingest import ingest_resource
from core.schemas import Rubric
from core.ui import friendly_errors, guard

st.set_page_config(page_title="MarkSense | Teacher setup", layout="wide")
teacher = guard("teacher")
st.title("Classrooms and assignments")
with st.form("classroom"):
    name = st.text_input("New classroom name")
    if st.form_submit_button("Create classroom"):
        with friendly_errors(), session_scope() as session:
            classroom = create_classroom(session, teacher, name)
            st.success(f"Created {classroom.name}. Join code: {classroom.join_code}")
with session_scope() as session:
    classrooms = list(session.scalars(select(Classroom).where(Classroom.teacher_id == teacher.id)))
if not classrooms:
    st.info("Create a classroom to get started.")
    st.stop()
classroom = st.selectbox("Classroom", classrooms, format_func=lambda c: c.name)
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

st.subheader("Create an assignment or exam")
title = st.text_input("Title")
assignment_kind = st.selectbox("Kind", ["assignment", "exam"])
has_due_date = st.checkbox("Set a due date")
due = st.date_input("Due date") if has_due_date else None
method = st.radio("Rubric input", ["Visual builder", "Paste JSON"], horizontal=True)
if method == "Visual builder":
    exam_max = st.number_input("Exam maximum", min_value=0.5, value=20.0, step=0.5)
    count = st.number_input("Number of questions", 1, 30, 3)
    questions = []
    for i in range(1, count + 1):
        with st.expander(f"Q{i}", expanded=i == 1):
            q_text = st.text_area("Question text", key=f"text_{i}")
            q_max = st.number_input("Question maximum", min_value=0.5, value=5.0 if i < 3 else 10.0, step=0.5, key=f"max_{i}")
            q_type = st.selectbox("Question type", ["descriptive", "mcq"], key=f"type_{i}")
            group = st.text_input("Optional group (blank for compulsory)", key=f"group_{i}").strip() or None
            n = st.number_input("Number of criteria", 1, 15, 1, key=f"n_{i}")
            criteria = []
            for j in range(1, n + 1):
                label = st.text_input(f"Criterion {j} name", value="Correct explanation", key=f"cname_{i}_{j}")
                description = st.text_input(f"Criterion {j} description", value="Explains the concept using the notes", key=f"cdesc_{i}_{j}")
                maximum = st.number_input(f"Criterion {j} maximum", min_value=0.5, value=float(q_max / n), key=f"cmax_{i}_{j}")
                criteria.append({"id": f"Q{i}.c{j}", "name": label, "max": maximum, "description": description})
            questions.append({"id": f"Q{i}", "text": q_text, "max": q_max, "type": q_type, "optional_group": group, "criteria": criteria})
    groups = {}
    for group in sorted({q["optional_group"] for q in questions if q["optional_group"]}):
        members = sum(q["optional_group"] == group for q in questions)
        attempt = st.number_input(f"{group}: attempt count", 1, members, members, key=f"attempt_{group}")
        pick = st.selectbox(f"{group}: selection", ["best", "first"], key=f"pick_{group}")
        groups[group] = {"attempt": attempt, "pick": pick}
    carry = st.checkbox("Award carry-forward method credit", value=True)
    negative = st.checkbox("Enable negative marking for MCQ")
    penalty = st.number_input("Penalty per wrong MCQ", 0.0, value=0.25, step=0.25)
    rounding = st.number_input("Round each question to", min_value=0.01, value=0.5, step=0.1)
    raw = {"exam_max": exam_max, "questions": questions, "rules": {"carry_forward": carry,
           "optional_groups": groups, "negative_marking": {"enabled": negative, "per_wrong": penalty, "applies_to": "mcq"}, "round_to": rounding}}
else:
    text = st.text_area("Rubric JSON", height=350, placeholder='{"exam_max": 20, "questions": [...]}')
    raw = None
    if text.strip():
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
rubric = None
if raw is not None:
    try:
        rubric = Rubric.model_validate(raw)
    except ValidationError as exc:
        st.error("Invalid rubric: " + str(exc))
if st.button("Create assignment", disabled=rubric is None or not title.strip()):
    with friendly_errors(), session_scope() as session:
        owned_classroom(session, classroom.id, teacher)
        session.add(Assignment(classroom_id=classroom.id, title=title.strip(), kind=assignment_kind,
                    rubric_json=rubric.model_dump(), max_marks=rubric.exam_max,
                    due_date=datetime.combine(due, time.max) if due else None))
        st.success("Assignment created.")
with session_scope() as session:
    assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id == classroom.id)))
for assignment in assignments:
    st.caption(f"{assignment.title} · {assignment.kind} · maximum {assignment.max_marks:g}")
