"""Distinct teacher and student overviews with scoped, live workspace data."""
from html import escape
from sqlalchemy import select
import streamlit as st
from core.db import Assignment, Classroom, Enrollment, Submission, session_scope
from core.ui import empty_state, guard, page_header


def teacher_dashboard() -> None:
    """Give teachers their classroom summary and review workload."""
    teacher = guard("teacher")
    page_header(f"Welcome back, {teacher.name.split()[0]}.", "A little clarity for your classroom. Everything you need to teach, assess, and guide.", "TEACHER WORKSPACE")
    with session_scope() as session:
        classrooms = list(session.scalars(select(Classroom).where(Classroom.teacher_id == teacher.id)))
        ids = [c.id for c in classrooms]
        assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id.in_(ids)).order_by(Assignment.id.desc())))
        enrollments = list(session.scalars(select(Enrollment).where(Enrollment.classroom_id.in_(ids))))
        submissions = list(session.scalars(select(Submission).where(Submission.assignment_id.in_([a.id for a in assignments]), Submission.mode == "final")))
    awaiting = sum(s.status == "graded" for s in submissions)
    for column, label, value in zip(st.columns(4), ["Classrooms", "Students", "Assignments", "Awaiting review"],
                                    [len(classrooms), len({e.student_id for e in enrollments}), len(assignments), awaiting]):
        column.metric(label, value)
    st.write("")
    left, right = st.columns([1.65, 1], gap="large")
    with left, st.container(border=True):
        st.subheader("Your assignments")
        st.caption("An overview of what your classes are working on.")
        if not assignments:
            empty_state("Your classroom starts here", "Create a classroom, add your resources, and set the first assignment.")
        else:
            names = {c.id:c.name for c in classrooms}
            for assignment in assignments[:5]:
                count = sum(s.assignment_id == assignment.id and s.status == "graded" for s in submissions)
                st.markdown(f'<div class="activity-row"><div><strong>{escape(assignment.title)}</strong>'
                            f'<small>{escape(names[assignment.classroom_id])} · {escape(assignment.kind.title())}</small></div>'
                            f'<span class="status-pill">{count} to review</span></div>', unsafe_allow_html=True)
        st.page_link("pages/1_Teacher_Setup.py", label="Manage classrooms & assignments", icon=":material/arrow_forward:")
    with right:
        title = "Ready for your review." if awaiting else "Set learning in motion."
        text = f"{awaiting} final submissions are waiting for your judgement and approval." if awaiting else "Bring your teaching materials and criteria together in a classroom."
        st.markdown(f'<div class="focus-card"><div class="eyebrow">YOUR NEXT STEP</div><h2>{title}</h2><p>{text}</p><span>Clear criteria. Thoughtful feedback.</span></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("Review with context")
            st.caption("Student answers, source evidence, and criterion decisions, together in one place.")
            st.page_link("pages/3_Teacher_Review.py", label="Open review queue", icon=":material/fact_check:")


def student_dashboard() -> None:
    """Show students their work and feedback without teacher tools."""
    student = guard("student")
    page_header(f"Hello, {student.name.split()[0]}.", "Make your next attempt your best one. Your assignments and feedback, all in one place.", "STUDENT WORKSPACE")
    with session_scope() as session:
        classrooms = list(session.scalars(select(Classroom).join(Enrollment).where(Enrollment.student_id == student.id)))
        assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id.in_([c.id for c in classrooms])).order_by(Assignment.id.desc())))
        attempts = list(session.scalars(select(Submission).where(Submission.student_id == student.id).order_by(Submission.created_at.desc())))
    for column, label, value in zip(st.columns(3), ["My classrooms", "Assignments", "Feedback ready"],
                                    [len(classrooms), len(assignments), sum(a.status == "approved" or (a.mode == "draft" and bool(a.hints_json)) for a in attempts)]):
        column.metric(label, value)
    st.write("")
    left, right = st.columns([1.65, 1], gap="large")
    with left, st.container(border=True):
        st.subheader("What's next")
        st.caption("Find your assignment and take the next step.")
        if not assignments:
            empty_state("You're ready to begin", "Join a classroom using the code from your teacher. Your assignments will appear here.")
        else:
            names = {c.id:c.name for c in classrooms}
            for assignment in assignments[:5]:
                latest = next((a for a in attempts if a.assignment_id == assignment.id and a.mode == "final"), None)
                status = {"uploaded":"File uploaded", "transcribed":"Ready to submit", "graded":"In review",
                          "approved":"Feedback ready", "rejected":"Changes requested"}.get(latest.status, "In progress") if latest else "Ready to start"
                st.markdown(f'<div class="activity-row"><div><strong>{escape(assignment.title)}</strong><small>{escape(names[assignment.classroom_id])}</small></div>'
                            f'<span class="status-pill">{escape(status)}</span></div>', unsafe_allow_html=True)
        st.page_link("pages/2_Student_Submit.py", label="Open assignments & submit work", icon=":material/arrow_forward:")
    with right:
        st.markdown('<div class="focus-card"><div class="eyebrow">PROGRESS, ONE STEP AT A TIME</div><h2>Start with a draft.</h2>'
                    '<p>Get a nudge in the right direction before you submit your final work.</p><span>Reflect. Revise. Try again.</span></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("Feedback you can use")
            st.caption("Find your teacher-approved results and a focused revision plan.")
            st.page_link("pages/4_Student_Report.py", label="View my feedback", icon=":material/auto_stories:")
