"""MarkSense entry point with account-scoped navigation."""
import streamlit as st

from core.access import access_page
from core.config import AppError, ROOT, get_settings
from core.dashboard import student_dashboard, teacher_dashboard
from core.db import User, session_scope
from core.navigation import workspace_pages
from core.ui import account_sidebar, apply_theme, friendly_errors

st.set_page_config(page_title="MarkSense", page_icon="✦", layout="wide")
apply_theme()
try:
    settings = get_settings()
except AppError as exc:
    st.error(str(exc))
    st.stop()


@st.cache_resource
def initialize_indexes(data_directory: str) -> str:
    """Initialize lexical indexes once per configured workspace."""
    from core.retrieval import rebuild_indexes
    rebuild_indexes()
    return data_directory


with friendly_errors():
    initialize_indexes(str(settings.data_dir))
with session_scope() as session:
    current = session.get(User, st.session_state.get("user_id", -1))

if current is None:
    # Explicit navigation disables the automatic pages/ directory menu.
    st.navigation([st.Page(access_page, title="Welcome to MarkSense", default=True)], position="hidden").run()
else:
    st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "mark.svg"))
    home = teacher_dashboard if current.role == "teacher" else student_dashboard
    pages = [st.Page(home, title="Classes",
                     icon=":material/space_dashboard:", default=True)]
    pages.extend(st.Page(spec.path, title=spec.title, icon=spec.icon, url_path=spec.url)
                 for spec in workspace_pages(current.role))
    selected = st.navigation({"TEACHING" if current.role == "teacher" else "LEARNING": pages}, expanded=True)
    account_sidebar(current)
    selected.run()
