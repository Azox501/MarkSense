import pytest
from pydantic import ValidationError

from core.config import AppError
from core.ingest import chunk_pages, read_pdf
from core.schemas import Rubric


def test_question_chunking():
    chunks = chunk_pages(["Q1 Define force. " + "force " * 500, "continued text\nQuestion 2 Define work."])
    assert chunks[0][1] == "Q1"
    assert chunks[-1][1] == "Q2"
    assert chunks[-1][2] == 2
    assert any(q == "Q1" and p == 2 for _, q, p in chunks)


def test_bad_pdf():
    with pytest.raises(AppError):
        read_pdf(b"")
    with pytest.raises(AppError):
        read_pdf(b"not a pdf")


def test_invalid_rubric():
    with pytest.raises(ValidationError):
        Rubric.model_validate({"exam_max": -1, "questions": []})


def test_identical_upload_does_not_duplicate_chunks(local_db, monkeypatch):
    import fitz
    from sqlalchemy import func, select
    from core import ingest
    from core.auth import create_classroom, register
    from core.db import Chunk, Resource, session_scope
    calls = []
    class Store:
        def upsert(self, **kwargs): calls.append(kwargs)
        def delete(self, **kwargs): pass
    monkeypatch.setattr(ingest,"collection",lambda _: Store())
    monkeypatch.setattr(ingest,"embed",lambda texts: [[1.0,0.0] for _ in texts])
    with session_scope() as session:
        teacher = register(session,"Teacher","teacher@example.test","password123","teacher")
        classroom = create_classroom(session,teacher,"Physics")
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50,50),"Q1 Force is a push or pull. F equals mass times acceleration.")
        data = pdf.tobytes()
    first = ingest.ingest_resource(teacher,classroom.id,"notes","notes.pdf",data)
    second = ingest.ingest_resource(teacher,classroom.id,"notes","renamed.pdf",data)
    assert first == second and len(calls) == 1
    with session_scope() as session:
        assert session.scalar(select(func.count(Resource.id))) == 1
        assert session.scalar(select(func.count(Chunk.id))) == len(calls[0]["ids"])
