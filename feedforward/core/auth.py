"""Authentication and authorization enforced in services as well as pages."""
import secrets
import string

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import AppError, get_settings
from core.db import Assignment, Classroom, Enrollment, User


def register(session: Session, name: str, email: str, password: str, role: str) -> User:
    """Create a local account with a salted bcrypt password hash."""
    email = email.strip().lower()
    if not name.strip() or "@" not in email or role not in {"teacher", "student"}:
        raise AppError("Enter a name, valid email and account role.")
    if not 8 <= len(password.encode()) <= 72:
        raise AppError("Password must be between 8 and 72 UTF-8 bytes.")
    if session.scalar(select(User).where(User.email == email)):
        raise AppError("That email is already registered.")
    user = User(name=name.strip(), email=email, role=role,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    session.add(user)
    session.flush()
    return user


def login(session: Session, email: str, password: str) -> User:
    """Check a password without exposing whether the email exists."""
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or len(password.encode()) > 72 or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise AppError("Email or password is incorrect.")
    return user


def require_role(user: User, role: str) -> None:
    """Reject service calls from the wrong account role."""
    if user.role != role:
        raise AppError(f"This action requires a {role} account.")


def owned_classroom(session: Session, classroom_id: int, teacher: User) -> Classroom:
    """Check classroom ownership for every teacher operation."""
    require_role(teacher, "teacher")
    classroom = session.get(Classroom, classroom_id)
    if not classroom or classroom.teacher_id != teacher.id:
        raise AppError("You do not have access to this classroom.")
    return classroom


def enrolled_assignment(session: Session, assignment_id: int, student: User) -> Assignment:
    """Check student membership before reading an assignment or submitting work."""
    require_role(student, "student")
    assignment = session.get(Assignment, assignment_id)
    if not assignment or not session.scalar(select(Enrollment).where(
            Enrollment.classroom_id == assignment.classroom_id, Enrollment.student_id == student.id)):
        raise AppError("Join the classroom before opening this assignment.")
    return assignment


def create_classroom(session: Session, teacher: User, name: str) -> Classroom:
    """Create a classroom with a unique six-character join code."""
    require_role(teacher, "teacher")
    if not name.strip():
        raise AppError("Enter a classroom name.")
    while True:
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if not session.scalar(select(Classroom.id).where(Classroom.join_code == code)):
            break
    classroom = Classroom(name=name.strip(), teacher_id=teacher.id, join_code=code,
                          similarity_threshold=get_settings(False).similarity_threshold)
    session.add(classroom)
    session.flush()
    return classroom


def join_classroom(session: Session, student: User, code: str) -> Classroom:
    """Enroll a student once, rejecting an unknown code."""
    require_role(student, "student")
    classroom = session.scalar(select(Classroom).where(Classroom.join_code == code.strip().upper()))
    if not classroom:
        raise AppError("Invalid classroom code. Ask your teacher for the six-character code.")
    if not session.scalar(select(Enrollment).where(Enrollment.classroom_id == classroom.id,
                                                  Enrollment.student_id == student.id)):
        session.add(Enrollment(classroom_id=classroom.id, student_id=student.id))
    return classroom


def add_student(session: Session, teacher: User, classroom_id: int, email: str) -> None:
    """Let a teacher enroll an existing student account by email."""
    classroom = owned_classroom(session, classroom_id, teacher)
    student = session.scalar(select(User).where(User.email == email.strip().lower(), User.role == "student"))
    if not student:
        raise AppError("Ask the student to register first, then add their email.")
    join_classroom(session, student, classroom.join_code)
