"""Distinct teacher and student overviews with scoped, live workspace data."""
from html import escape
from sqlalchemy import select
import streamlit as st
from core.db import Assignment, Classroom, Enrollment, Submission, session_scope
from core.ui import empty_state, guard, page_header


def teacher_dashboard() -> None:
    """Give teachers their classroom summary and review workload."""
    teacher = guard("teacher")
    page_header("Classes", f"Good to see you, {teacher.name.split()[0]}. Manage your classes and keep up with student work.", "TEACHER")
    with session_scope() as session:
        classrooms = list(session.scalars(select(Classroom).where(Classroom.teacher_id == teacher.id)))
        ids = [c.id for c in classrooms]
        assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id.in_(ids)).order_by(Assignment.id.desc())))
        enrollments = list(session.scalars(select(Enrollment).where(Enrollment.classroom_id.in_(ids))))
        submissions = list(session.scalars(select(Submission).where(Submission.assignment_id.in_([a.id for a in assignments]), Submission.mode == "final")))
    awaiting = sum(s.status == "graded" for s in submissions)
    st.markdown('<div class="classroom-toolbar"><h2>Your classes</h2><span>Choose a class to manage its work</span></div>', unsafe_allow_html=True)
    if not classrooms:
        empty_state("Create your first class", "Add a class, invite students, and post your first assignment.", "school")
    else:
        cards = st.columns(min(3, len(classrooms)), gap="large")
        for index, classroom in enumerate(classrooms):
            class_assignments = [a for a in assignments if a.classroom_id == classroom.id]
            class_students = sum(e.classroom_id == classroom.id for e in enrollments)
            with cards[index % len(cards)]:
                st.markdown(f'<div class="classroom-card classroom-card-{index % 4}"><div class="classroom-card-banner">'
                            f'<span class="classroom-card-label">{escape(classroom.name)}</span>'
                            f'<small>{class_students} student{"s" if class_students != 1 else ""}</small></div>'
                            f'<div class="classroom-card-body"><strong>{len(class_assignments)} assignment'
                            f'{"s" if len(class_assignments) != 1 else ""}</strong><span>Join code: {escape(classroom.join_code)}</span></div></div>',
                            unsafe_allow_html=True)
                st.page_link("pages/1_Teacher_Setup.py", label="Open class", icon=":material/arrow_forward:", width="stretch")
    st.markdown('<div class="classroom-toolbar stream-heading"><h2>To review</h2><span>Recent final submissions from your classes</span></div>', unsafe_allow_html=True)
    if awaiting:
        names = {c.id: c.name for c in classrooms}
        for assignment in assignments[:5]:
            count = sum(s.assignment_id == assignment.id and s.status == "graded" for s in submissions)
            if count:
                st.markdown(f'<div class="stream-item"><span class="stream-icon">✓</span><div><strong>{escape(assignment.title)}</strong>'
                            f'<small>{escape(names[assignment.classroom_id])}</small></div><span class="status-pill">{count} to review</span></div>',
                            unsafe_allow_html=True)
        st.page_link("pages/3_Teacher_Review.py", label="Open review queue", icon=":material/fact_check:")
    else:
        empty_state("Nothing to review", "Final submissions from your students will appear here.", "done")


def student_dashboard() -> None:
    """Show students their work and feedback without teacher tools."""
    student = guard("student")
    page_header("Classes", f"Hello, {student.name.split()[0]}. See your classwork and feedback in one place.", "STUDENT")
    with session_scope() as session:
        classrooms = list(session.scalars(select(Classroom).join(Enrollment).where(Enrollment.student_id == student.id)))
        assignments = list(session.scalars(select(Assignment).where(Assignment.classroom_id.in_([c.id for c in classrooms])).order_by(Assignment.id.desc())))
        attempts = list(session.scalars(select(Submission).where(Submission.student_id == student.id).order_by(Submission.created_at.desc())))
    st.markdown('<div class="classroom-toolbar"><h2>Your classes</h2><span>Open a class to view its work</span></div>', unsafe_allow_html=True)
    if not classrooms:
        empty_state("Join a class", "Use the code shared by your teacher. Your classwork will appear here.", "school")
    else:
        cards = st.columns(min(3, len(classrooms)), gap="large")
        for index, classroom in enumerate(classrooms):
            class_assignments = [a for a in assignments if a.classroom_id == classroom.id]
            with cards[index % len(cards)]:
                st.markdown(f'<div class="classroom-card classroom-card-{index % 4}"><div class="classroom-card-banner">'
                            f'<span class="classroom-card-label">{escape(classroom.name)}</span><small>Classwork</small></div>'
                            f'<div class="classroom-card-body"><strong>{len(class_assignments)} assignment'
                            f'{"s" if len(class_assignments) != 1 else ""}</strong><span>Stay on top of your work</span></div></div>',
                            unsafe_allow_html=True)
                st.page_link("pages/2_Student_Submit.py", label="View classwork", icon=":material/arrow_forward:", width="stretch")
    st.markdown('<div class="classroom-toolbar stream-heading"><h2>Upcoming work</h2><span>Assignments from your classes</span></div>', unsafe_allow_html=True)
    if not assignments:
        empty_state("No classwork yet", "When your teacher posts an assignment, it will appear here.", "assignment")
    else:
        names = {c.id: c.name for c in classrooms}
        for assignment in assignments[:8]:
            latest = next((a for a in attempts if a.assignment_id == assignment.id and a.mode == "final"), None)
            status = ({"uploaded": "File uploaded", "transcribed": "Ready to submit", "graded": "In review",
                       "approved": "Feedback ready", "rejected": "Changes requested"}.get(latest.status, "In progress")
                      if latest else "Ready to start")
            st.markdown(f'<div class="stream-item"><span class="stream-icon">≡</span><div><strong>{escape(assignment.title)}</strong>'
                        f'<small>{escape(names[assignment.classroom_id])} · {assignment.max_marks:g} marks</small></div>'
                        f'<span class="status-pill">{escape(status)}</span></div>', unsafe_allow_html=True)
        st.page_link("pages/2_Student_Submit.py", label="Open classwork", icon=":material/assignment:")
