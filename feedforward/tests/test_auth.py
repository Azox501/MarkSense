import pytest

from core.auth import add_student, create_classroom, join_classroom, login, register, require_role
from core.config import AppError
from core.db import session_scope


def test_auth_and_membership(local_db):
    with session_scope() as session:
        teacher = register(session, "Teacher", "teacher@example.test", "demo12345", "teacher")
        student = register(session, "Student", "student@example.test", "demo12345", "student")
        assert student.password_hash.startswith("$2")
        assert login(session, student.email, "demo12345").id == student.id
        with pytest.raises(AppError):
            login(session, student.email, "wrong")
        with pytest.raises(AppError):
            require_role(student, "teacher")
        with pytest.raises(AppError):
            require_role(teacher, "student")
        classroom = create_classroom(session, teacher, "Demo")
        assert len(classroom.join_code) == 6
        assert join_classroom(session, student, classroom.join_code).id == classroom.id
        with pytest.raises(AppError, match="Invalid"):
            join_classroom(session, student, "BADBAD")
        add_student(session, teacher, classroom.id, student.email)
