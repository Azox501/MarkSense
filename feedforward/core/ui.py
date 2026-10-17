"""Shared Streamlit guards and safe error display."""
from contextlib import contextmanager
from html import escape
import logging
from typing import Iterator

import streamlit as st

from core.config import AppError, ROOT, get_settings
from core.db import User, session_scope


def apply_theme() -> None:
    """Load shared styling from a local asset without external font requests."""
    st.markdown("<style>" + (ROOT / "assets" / "theme.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)


def page_header(title: str, description: str, section: str) -> None:
    """Render consistent page hierarchy with escaped account-supplied text."""
    st.markdown(f'<div class="page-heading"><div class="eyebrow">{escape(section)}</div>'
                f'<h1>{escape(title)}</h1><p>{escape(description)}</p></div>', unsafe_allow_html=True)


def empty_state(title: str, description: str, icon: str = "✦") -> None:
    """Display a useful empty workspace without sample content."""
    st.markdown(f'<div class="empty-state"><span>{escape(icon)}</span><h3>{escape(title)}</h3>'
                f'<p>{escape(description)}</p></div>', unsafe_allow_html=True)


def account_sidebar(user: User) -> None:
    """Show identity and a shared sign-out action for the current role."""
    with st.sidebar.container(key="account_panel"):
        initials = "".join(word[0] for word in user.name.split()[:2]).upper()
        st.markdown(f'<div class="account-card"><div class="avatar">{escape(initials)}</div><div>'
                    f'<strong>{escape(user.name)}</strong><small>{escape(user.role.title())} workspace</small></div></div>', unsafe_allow_html=True)
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            st.session_state.clear()
            st.rerun()


def guard(role: str) -> User:
    """Resolve the current local user and stop unauthorized page execution."""
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
