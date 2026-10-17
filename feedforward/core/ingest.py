"""PDF validation, classroom-scoped chunking and idempotent local indexing."""
from collections.abc import Callable
import hashlib
from pathlib import Path
import re
from typing import TYPE_CHECKING

import fitz
from sqlalchemy import select

from core.auth import owned_classroom
from core.config import AppError, get_settings
from core.db import Chunk, Resource, User, session_scope
from core.models import embed

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

QUESTION = re.compile(r"(?im)(?:^|\n)\s*(?:Q(?:uestion)?\s*|Ans(?:wer)?\s*)(\d+)\b[.\s:)-]*")


def read_pdf(data: bytes) -> fitz.Document:
    """Validate an unencrypted, nonempty PDF with a practical upload limit."""
    if not data or len(data) > 30 * 1024 * 1024:
        raise AppError("Upload a nonempty PDF smaller than 30 MB.")
    try:
        document = fitz.open(stream=data, filetype="pdf")
        if document.needs_pass or not 1 <= len(document) <= 100:
            document.close()
            raise AppError("Use an unlocked PDF with 1–100 pages.")
        return document
    except (RuntimeError, ValueError) as exc:
        raise AppError("This PDF could not be read. Export it as a new PDF and try again.") from exc


def chunk_pages(pages: list[str], size: int = 300, overlap: int = 50) -> list[tuple[str, str | None, int]]:
    """Split on question markers, then use overlapping approximate-token windows."""
    if size <= overlap or overlap < 0:
        raise ValueError("Chunk size must exceed the nonnegative overlap.")
    result: list[tuple[str, str | None, int]] = []
    current_question: str | None = None
    for page_no, text in enumerate(pages, 1):
        markers = list(QUESTION.finditer(text))
        sections: list[tuple[str, str | None]] = []
        start = 0
        for marker in markers:
            sections.append((text[start:marker.start()], current_question))
            current_question = "Q" + marker.group(1)
            start = marker.start()
        sections.append((text[start:], current_question))
        for section, question_no in sections:
            words = section.split()
            # About 1.3 subword tokens per word; window ~= 300 tokens, overlap ~= 50.
            window, stride = max(1, int(size / 1.3)), max(1, int((size - overlap) / 1.3))
            for offset in range(0, len(words), stride):
                result.append((" ".join(words[offset:offset + window]), question_no, page_no))
                if offset + window >= len(words):
                    break
    return result


def collection(classroom_id: int) -> "Collection":
    """Open the classroom's persistent Chroma collection with telemetry disabled."""
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(get_settings(False).data_dir / "chroma"),
                                       settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(f"classroom_{classroom_id}", embedding_function=None,
                                           metadata={"hnsw:space": "cosine"})


def ingest_resource(teacher: User, classroom_id: int, kind: str, filename: str, data: bytes,
                    progress: Callable[[float], None] = lambda _: None) -> int:
    """Persist and index a PDF once per classroom, resource kind and content hash."""
    if kind not in {"answer_key", "notes", "question_paper"}:
        raise AppError("Select answer key, notes or question paper.")
    digest = hashlib.sha256(data).hexdigest()
    with session_scope() as session:
        owned_classroom(session, classroom_id, teacher)
        existing = session.scalar(select(Resource).where(Resource.classroom_id == classroom_id,
                                  Resource.kind == kind, Resource.content_hash == digest))
        if existing:
            progress(1.0)
            return existing.id
    with read_pdf(data) as document:
        pages = []
        for index, page in enumerate(document):
            text = page.get_text().strip()
            if len(text) < 20:
                from core.local_ocr import recognize_image
                text = recognize_image(page.get_pixmap(dpi=200).tobytes("png"))
            pages.append(text)
            progress(0.4 * (index + 1) / len(document))
    pieces = chunk_pages(pages)
    if not pieces:
        raise AppError("No text was found in this resource.")
    vectors = embed([text for text, _, _ in pieces])
    progress(0.7)
    directory = get_settings(False).data_dir / "uploads" / str(classroom_id) / "resources"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{kind}_{digest}.pdf"
    path.write_bytes(data)
    ids = [f"{classroom_id}_{kind}_{digest}_{i}" for i in range(len(pieces))]
    store = collection(classroom_id)
    try:
        with session_scope() as session:
            resource = Resource(classroom_id=classroom_id, kind=kind, filename=Path(filename).name,
                                path=str(path), content_hash=digest)
            session.add(resource)
            session.flush()
            for chroma_id, (text, question, page_no) in zip(ids, pieces):
                session.add(Chunk(resource_id=resource.id, classroom_id=classroom_id, text=text,
                                  question_no=question, page=page_no, chroma_id=chroma_id))
            store.upsert(ids=ids, documents=[p[0] for p in pieces], embeddings=vectors,
                         metadatas=[{"kind": kind, "page": p[2], "question_no": p[1] or ""} for p in pieces])
            resource_id = resource.id
    except Exception:
        store.delete(ids=ids)
        raise
    progress(1.0)
    return resource_id
