"""Idempotent dummy demo accounts, physics PDFs and four transcribed attempts."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
from sqlalchemy import select

from core.auth import create_classroom, join_classroom, register
from core.config import get_settings
from core.db import Assignment, Classroom, Submission, User, session_scope
from core.ingest import ingest_resource
from core.schemas import Rubric, Transcript

PASSWORD = "FeedForwardDemo123!"
NOTES = """Q1 Force
Force is a push or pull that changes the motion of an object. Newton's second law states F = m a.
Mass is measured in kilograms, acceleration in metres per second squared, and force in newtons (N).
Q2 Work
Work is done when a force causes displacement. For a force parallel to motion, W = F s.
The SI unit of work is the joule. If F is 5 N and s is 2 m, W is 10 J.
Q3 Kinetic energy
Kinetic energy is the energy of motion. KE = 0.5 m v squared. Show substitution and evaluate with units.
For mass 2 kg and speed 3 m/s, KE = 0.5 times 2 times 9 = 9 J.
Carry-forward method credit is appropriate if a student uses a correct method with an earlier numerical error."""
KEY = """Q1 Definition: push or pull changing motion. Formula: F = m a. Unit: newton (N).
Q2 Use W = F s with F = 5 N and s = 2 m. Result: 10 J.
Q3 Use KE = 0.5 m v squared and substitute 2 kg, 3 m/s. Result: 9 J."""
PAPER = """Q1 Define force, give its formula and SI unit.
Q2 A force of 5 N moves an object 2 m in the direction of the force. Calculate the work done with units.
Q3 Calculate the kinetic energy of a 2 kg object moving at 3 m/s. Show your method and units."""


def demo_rubric() -> Rubric:
    """Return the three-question, twenty-mark demo rubric."""
    specs = [("Q1",5,[('Definition',2,'Defines force as a push or pull changing motion'),('Formula',2,'States F = m a'),('Units',1,'Uses newtons')]),
             ("Q2",5,[('Method',3,'Uses W = F s and substitutes 5 N and 2 m'),('Result and units',2,'Gets 10 J')]),
             ("Q3",10,[('Method',6,'Uses KE = 0.5 m v squared with correct substitution'),('Result and units',4,'Gets 9 J')])]
    texts = PAPER.splitlines()
    return Rubric.model_validate({"exam_max":20,"questions":[{"id":qid,"text":text,"max":maximum,
        "criteria":[{"id":f"{qid}.c{i}","name":name,"max":marks,"description":description}
                    for i,(name,marks,description) in enumerate(criteria,1)]}
        for (qid,maximum,criteria),text in zip(specs,texts)]})


def make_pdf(path: Path, text: str, image_only: bool = False) -> None:
    """Create typed PDFs and a raster-only synthetic handwriting-style fixture."""
    with fitz.open() as document:
        page = document.new_page()
        font = Path("C:/Windows/Fonts/segoepr.ttf")
        options = {"fontname":"hand", "fontfile":str(font)} if image_only and font.exists() else {"fontname":"heit" if image_only else "helv"}
        result = page.insert_textbox(fitz.Rect(45,45,550,790), text, fontsize=12, **options)
        if result < 0:
            raise RuntimeError("Demo PDF text exceeded page capacity.")
        if image_only:
            image = page.get_pixmap(dpi=160).tobytes("png")
            with fitz.open() as raster:
                target = raster.new_page()
                target.insert_image(target.rect, stream=image)
                raster.save(str(path))
        else:
            document.save(str(path))


def main() -> None:
    """Seed local fixtures; optionally postpone indexing until models are installed."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-only", action="store_true", help="Create accounts/PDFs without indexing; rerun normally after model download")
    args = parser.parse_args()
    directory = get_settings(False).data_dir / "demo"
    directory.mkdir(parents=True, exist_ok=True)
    rubric = demo_rubric()
    with session_scope() as session:
        teacher = session.scalar(select(User).where(User.email == "teacher@demo.test"))
        if teacher is None:
            teacher = register(session,"Demo Teacher","teacher@demo.test",PASSWORD,"teacher")
        students = []
        for i,name in enumerate(["Asha Demo","Ben Demo","Chen Demo","Divya Demo"],1):
            email = f"student{i}@demo.test"
            student = session.scalar(select(User).where(User.email == email))
            students.append(student or register(session,name,email,PASSWORD,"student"))
        classroom = session.scalar(select(Classroom).where(Classroom.teacher_id == teacher.id, Classroom.name == "Demo Physics"))
        if classroom is None:
            classroom = create_classroom(session,teacher,"Demo Physics")
        for student in students:
            join_classroom(session,student,classroom.join_code)
        assignment = session.scalar(select(Assignment).where(Assignment.classroom_id == classroom.id,Assignment.title == "Physics diagnostic"))
        if assignment is None:
            assignment = Assignment(classroom_id=classroom.id,title="Physics diagnostic",kind="exam",
                                    rubric_json=rubric.model_dump(),max_marks=20)
            session.add(assignment)
            session.flush()
        classroom_id, assignment_id = classroom.id, assignment.id
        print(f"Classroom: {classroom.name}; join code: {classroom.join_code}")
    for kind,text in [("notes",NOTES),("answer_key",KEY),("question_paper",PAPER)]:
        path = directory / (kind + ".pdf")
        if not path.exists():
            make_pdf(path,text)
        if not args.fixtures_only:
            ingest_resource(teacher,classroom_id,kind,path.name,path.read_bytes())
    examples = [
        ["Force is a push or pull which changes motion. F = m a. The SI unit is N.","Work equals force times displacement, W = 5 times 2 = 10 J.","KE = 0.5 times m times v squared = 0.5 times 2 times 9 = 9 J."],
        ["Force is a push or pull which changes motion. F = m a. The SI unit is N.","Work equals force times displacement, W = 5 times 2 = 10 J.","KE = 0.5 times m times v squared = 0.5 times 2 times 9 = 9 J. Therefore nine joules."],
        ["I think force means the speed of an object.","The object moves two metres. I added five and two to get seven.","I used mass multiplied by speed and found six. I am unsure of the energy rule."],
        ["A push changes motion. F = m a. [illegible]", "W = F s = 5 x 2 = 10 J.","KE = 0.5 x 2 x 3 squared. My result is 6 J."]]
    folder = get_settings(False).data_dir / "uploads" / str(classroom_id) / str(assignment_id)
    folder.mkdir(parents=True, exist_ok=True)
    for index,(student,answers) in enumerate(zip(students,examples),1):
        path = folder / f"demo_student_{index}.pdf"
        if not path.exists():
            make_pdf(path,"\n\n".join(f"Q{i}\n{text}" for i,text in enumerate(answers,1)),image_only=index == 4)
        with session_scope() as session:
            if not session.scalar(select(Submission.id).where(Submission.assignment_id == assignment_id,
                Submission.student_id == student.id, Submission.file_path == str(path))):
                transcript = Transcript.model_validate({"answers":[{"question_id":f"Q{i}","text":answer,
                    "legibility":0.4 if "[illegible]" in answer else 0.98} for i,answer in enumerate(answers,1)]})
                session.add(Submission(assignment_id=assignment_id,student_id=student.id,mode="final",file_path=str(path),
                                       transcript_json=transcript.model_dump(),status="transcribed"))
    print("Teacher: teacher@demo.test; students: student1@demo.test through student4@demo.test")
    print("All demo passwords: " + PASSWORD)
    print("Fixture transcripts are prefilled, not Gemini results. Sign in as each student to confirm and process.")
    if args.fixtures_only:
        print("Resources NOT indexed. Rerun without --fixtures-only after installing the models.")


if __name__ == "__main__":
    main()
