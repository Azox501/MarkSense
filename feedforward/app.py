"""Streamlit entry point: registration, login and role routing."""
import streamlit as st

from core.auth import login, register
from core.config import AppError, get_settings
from core.db import User, session_scope
from core.ui import banner, friendly_errors

st.set_page_config(page_title="MarkSense", page_icon="📝", layout="wide")
st.title("MarkSense")
st.caption("AI judges with evidence. Code does the maths. The teacher has the final say.")
banner()
try:
    get_settings()
except AppError as exc:
    st.error(str(exc))
    st.info("Open README.md for setup instructions. Tests and the seed generator do not need API keys.")
    st.stop()

@st.cache_resource
def initialize_indexes() -> bool:
    """Rebuild local lexical indexes once per app process."""
    from core.retrieval import rebuild_indexes
    rebuild_indexes()
    return True

with friendly_errors():
    initialize_indexes()

with session_scope() as session:
    current = session.get(User, st.session_state.get("user_id", -1))
if current:
    st.success(f"Signed in as {current.name} ({current.role}).")
    if current.role == "teacher":
        st.page_link("pages/1_Teacher_Setup.py", label="Classroom and assignment setup")
        st.page_link("pages/3_Teacher_Review.py", label="Review and approve submissions")
    else:
        st.page_link("pages/2_Student_Submit.py", label="Join a classroom and submit")
        st.page_link("pages/4_Student_Report.py", label="My feedback and reports")
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()
else:
    sign_in, sign_up = st.tabs(["Sign in", "Register"])
    with sign_in, st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            with friendly_errors(), session_scope() as session:
                user = login(session, email, password)
                st.session_state["user_id"] = user.id
                st.rerun()
    with sign_up, st.form("register"):
        name = st.text_input("Name")
        email = st.text_input("Email", key="new_email")
        password = st.text_input("Password (8–72 bytes)", type="password", key="new_password")
        role = st.selectbox("Role", ["student", "teacher"])
        if st.form_submit_button("Create account"):
            with friendly_errors(), session_scope() as session:
                register(session, name, email, password, role)
                st.success("Account created. You can now sign in.")
