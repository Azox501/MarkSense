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
        return (WorkspacePage("pages/1_Teacher_Setup.py", "Classrooms & assignments", ":material/school:", "classrooms"),
                WorkspacePage("pages/3_Teacher_Review.py", "Review & results", ":material/fact_check:", "review"))
    if role == "student":
        return (WorkspacePage("pages/2_Student_Submit.py", "Submit work", ":material/upload_file:", "submit"),
                WorkspacePage("pages/4_Student_Report.py", "My feedback", ":material/auto_stories:", "feedback"))
    raise AppError("This account does not have a recognized workspace role.")
