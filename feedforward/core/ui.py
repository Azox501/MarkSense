"""Shared Streamlit guards and safe error display."""
from contextlib import contextmanager
import logging
from typing import Iterator

import streamlit as st

from core.config import AppError, get_settings
from core.db import User, session_scope


def banner() -> None:
    """Display the required dummy-data notice on every page."""
    st.warning("Demo mode: do not upload real student data.")


def guard(role: str) -> User:
    """Resolve the current local user and stop unauthorized page execution."""
    banner()
    try:
        get_settings()
    except AppError as exc:
        st.error(str(exc))
        st.stop()
    with session_scope() as session:
        user = session.get(User, st.session_state.get("user_id", -1))
        if not user or user.role != role:
            st.error(f"Sign in with a {role} account to open this page.")
            st.stop()
    if st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.switch_page("app.py")
    return user


@contextmanager
def friendly_errors() -> Iterator[None]:
    """Keep tracebacks out of the UI; technical diagnostics remain local."""
    try:
        yield
    except AppError as exc:
        st.error(str(exc))
    except Exception:
        logging.exception("Local operation failed")
        st.error("This operation could not finish. Check your setup and file, then retry. Details are in the local terminal.")
