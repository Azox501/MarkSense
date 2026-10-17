"""A single account sign-in routes each user to their own workspace."""
import streamlit as st
from core.auth import login, register
from core.db import session_scope
from core.ui import friendly_errors


def access_page() -> None:
    """Render a responsive account screen without workspace navigation."""
    st.markdown('<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}</style>', unsafe_allow_html=True)
    st.markdown('<div class="access-brand"><span class="brand-mark">✦</span> MarkSense</div>', unsafe_allow_html=True)
    introduction, form = st.container(key="access_layout").columns([1.15, 1], gap="large")
    with introduction:
        st.markdown("""<div class="access-intro">
          <div class="eyebrow">A CLEARER PATH TO PROGRESS</div>
          <h1>Make feedback <br>move learning <br><em class="accent">forward.</em></h1>
          <p>One place to connect classroom resources, thoughtful assessment,
             and the next step in every student's learning.</p>
          <div class="value-row"><span>01</span><div><strong>Grounded in your classroom</strong><p>Feedback connected to teaching materials and clear criteria.</p></div></div>
          <div class="value-row"><span>02</span><div><strong>Guidance that leads somewhere</strong><p>Useful draft hints and a focused plan for revision.</p></div></div>
          <div class="value-row"><span>03</span><div><strong>Teachers have the final say</strong><p>Every final result is reviewed before it is released.</p></div></div>
        </div>""", unsafe_allow_html=True)
    with form, st.container(border=True, key="access_form"):
        signup = st.session_state.get("access_screen") == "register"
        st.markdown('<div class="eyebrow">YOUR LEARNING, CONNECTED</div>', unsafe_allow_html=True)
        st.subheader("Create your account" if signup else "Welcome back.")
        st.caption("Choose your account type to get started." if signup else "Sign in to continue to your personal workspace.")
        if signup:
            with st.form("registration"):
                name = st.text_input("Full name", placeholder="Your name", autocomplete="name")
                email = st.text_input("Email address", placeholder="you@example.com", autocomplete="email")
                password = st.text_input("Password", type="password", help="Use between 8 and 72 UTF-8 bytes.", autocomplete="new-password")
                role = st.radio("Account type", ["Student", "Teacher"], horizontal=True)
                submitted = st.form_submit_button("Create account", type="primary", width="stretch")
            if submitted:
                with friendly_errors():
                    with session_scope() as session:
                        user_id = register(session, name, email, password, role.lower()).id
                    st.session_state.clear()
                    st.session_state["user_id"] = user_id
                    st.rerun()
            st.caption("Already have an account?")
            if st.button("Back to sign in", width="stretch"):
                st.session_state["access_screen"] = "login"
                st.rerun()
        else:
            with st.form("sign_in"):
                email = st.text_input("Email address", placeholder="you@example.com", autocomplete="email")
                password = st.text_input("Password", type="password", autocomplete="current-password")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                with friendly_errors():
                    with session_scope() as session:
                        user_id = login(session, email, password).id
                    st.session_state.clear()
                    st.session_state["user_id"] = user_id
                    st.rerun()
            st.caption("New to MarkSense?")
            if st.button("Create an account", width="stretch"):
                st.session_state["access_screen"] = "register"
                st.rerun()
        st.markdown('<div class="access-note">Your workspace is personal. Your account role determines the tools you see.</div>', unsafe_allow_html=True)
    st.markdown('<div class="access-footer">MarkSense &nbsp; / &nbsp; Thoughtful assessment. Meaningful progress.</div>', unsafe_allow_html=True)
