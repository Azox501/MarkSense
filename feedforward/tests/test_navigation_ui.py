"""Regression checks for role-specific navigation and the account lifecycle."""
import pytest
from streamlit.testing.v1 import AppTest

from core.auth import create_classroom, register
from core.config import AppError, ROOT, get_settings
from core.db import session_scope
from core.navigation import workspace_pages


def app_for_test(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_API_KEY", "local-ui-vision")
    monkeypatch.setenv("GEMINI_GRADER_API_KEY", "local-ui-grader")
    get_settings.cache_clear()
    return AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)


def click(app, label):
    return next(button for button in app.button if button.label == label).click().run(timeout=30)


def sign_in(app, email):
    app.text_input[0].set_value(email)
    app.text_input[1].set_value("password123")
    return click(app, "Sign in")


def test_routes_do_not_cross_roles():
    teacher = workspace_pages("teacher")
    student = workspace_pages("student")
    assert {p.path for p in teacher}.isdisjoint(p.path for p in student)
    assert all("Teacher" in p.path for p in teacher)
    assert all("Student" in p.path for p in student)
    with pytest.raises(AppError):
        workspace_pages("admin")


def test_signed_out_screen_hides_workspace_tools(local_db, monkeypatch):
    app = app_for_test(monkeypatch)
    assert not app.exception
    assert not app.sidebar.button
    assert not app.get("page_link")
    assert not app.radio  # Role selection belongs only to registration.
    assert not app.warning  # No permanent demo banner.
    assert [field.label for field in app.text_input] == ["Email address", "Password"]


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_sign_in_routes_to_separate_workspace_and_logout_clears_session(local_db, monkeypatch, role):
    with session_scope() as session:
        user = register(session, "Taylor Morgan", f"{role}@example.test", "password123", role)
        if role == "teacher":
            create_classroom(session, user, "My classroom")
            other = register(session, "Other Teacher", "other@example.test", "password123", "teacher")
            create_classroom(session, other, "Private classroom")
    app = sign_in(app_for_test(monkeypatch), user.email)
    assert not app.exception
    labels = {metric.label for metric in app.metric}
    if role == "teacher":
        assert "Awaiting review" in labels and "Feedback ready" not in labels
        assert next(m.value for m in app.metric if m.label == "Classrooms") == "1"
        allowed = "pages/1_Teacher_Setup.py"
        forbidden = "pages/2_Student_Submit.py"
    else:
        assert "Feedback ready" in labels and "Awaiting review" not in labels
        allowed = "pages/2_Student_Submit.py"
        forbidden = "pages/1_Teacher_Setup.py"
    app.switch_page(allowed).run(timeout=30)
    assert not app.exception
    with pytest.raises(ValueError):
        app.switch_page(forbidden)
    click(app, "Sign out")
    assert not app.exception
    assert "user_id" not in app.session_state
    assert not app.sidebar.button
    assert any(field.label == "Email address" for field in app.text_input)


@pytest.mark.parametrize("role", ["Teacher", "Student"])
def test_registration_opens_only_selected_role_workspace(local_db, monkeypatch, role):
    app = click(app_for_test(monkeypatch), "Create an account")
    app.text_input[0].set_value("Jordan Lee")
    app.text_input[1].set_value(f"{role.lower()}@example.test")
    app.text_input[2].set_value("password123")
    app.radio[0].set_value(role)
    click(app, "Create account")
    assert not app.exception
    labels = {metric.label for metric in app.metric}
    assert ("Awaiting review" in labels) == (role == "Teacher")
    assert ("Feedback ready" in labels) == (role == "Student")
