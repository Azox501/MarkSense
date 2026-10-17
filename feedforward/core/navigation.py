"""Role-specific routes; the opposite role's pages are never registered."""
from dataclasses import dataclass
from core.config import AppError


@dataclass(frozen=True)
class WorkspacePage:
    path: str
    title: str
    icon: str
    url: str


def workspace_pages(role: str) -> tuple[WorkspacePage, ...]:
    """Return only routes belonging to the authenticated account role."""
    if role == "teacher":
        return (WorkspacePage("pages/1_Teacher_Setup.py", "Manage classes", ":material/school:", "classes"),
                WorkspacePage("pages/3_Teacher_Review.py", "To review", ":material/fact_check:", "review"))
    if role == "student":
        return (WorkspacePage("pages/2_Student_Submit.py", "Classwork", ":material/assignment:", "classwork"),
                WorkspacePage("pages/4_Student_Report.py", "Grades & feedback", ":material/auto_stories:", "feedback"))
    raise AppError("This account does not have a recognized workspace role.")
