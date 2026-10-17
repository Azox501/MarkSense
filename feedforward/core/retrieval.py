"""Classroom-scoped dense/BM25 retrieval, reciprocal-rank fusion and reranking."""
from dataclasses import asdict, dataclass
import re
from threading import RLock
from typing import Any

from sqlalchemy import select

from core.config import get_settings
from core.db import Chunk, Resource, session_scope
from core.ingest import collection
from core.models import MODEL_LOCK, embed, reranking_model


@dataclass(frozen=True)
class Evidence:
    id: str
    text: str
    kind: str
    page: int
    question_no: str | None
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Serialize evidence for prompts and retained review snapshots."""
        return asdict(self)


def tokenize(text: str) -> list[str]:
    """Use consistent word tokenization for indexing and queries."""
    return re.findall(r"\w+", text.lower()) or [""]


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Fuse one-based ranks, counting each document once per ranking."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, document in enumerate(dict.fromkeys(ranking), 1):
            scores[document] = scores.get(document, 0.0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


_indexes: dict[int, tuple[tuple[str, ...], Any, list[Evidence]]] = {}
_index_lock = RLock()


def classroom_index(classroom_id: int) -> tuple[Any, list[Evidence]]:
    """Rebuild a classroom BM25 index when persisted chunk IDs change."""
    from rank_bm25 import BM25Okapi
    with session_scope() as session:
        rows = session.execute(select(Chunk, Resource.kind).join(Resource, Resource.id == Chunk.resource_id)
                               .where(Chunk.classroom_id == classroom_id).order_by(Chunk.id)).all()
    docs = [Evidence(c.chroma_id, c.text, kind, c.page, c.question_no) for c, kind in rows]
    signature = tuple(d.id for d in docs)
    with _index_lock:
        previous = _indexes.get(classroom_id)
        if previous and previous[0] == signature:
            return previous[1], previous[2]
        bm25 = BM25Okapi([tokenize(d.text) for d in docs]) if docs else None
        _indexes[classroom_id] = (signature, bm25, docs)
    return bm25, docs


def rebuild_indexes() -> None:
    """Build in-memory lexical indexes from SQLite at app startup."""
    with session_scope() as session:
        ids = list(session.scalars(select(Chunk.classroom_id).distinct()))
    for classroom_id in ids:
        classroom_index(classroom_id)


def retrieve(classroom_id: int, question_id: str, question_text: str, student_answer: str) -> list[Evidence]:
    """Fuse top-K rankings, prefer matching questions, rerank and retain a matching key."""
    settings = get_settings(False)
    bm25, docs = classroom_index(classroom_id)
    if not docs:
        return []
    if not question_text:
        question_text = " ".join(d.text for d in docs if d.kind == "question_paper" and d.question_no == question_id)
    query = (question_text + "\n" + student_answer).strip() or question_id
    vectors = embed([query], query=True)
    dense = collection(classroom_id).query(query_embeddings=vectors,
                 n_results=min(settings.retrieve_top_k, len(docs)), include=["distances"])["ids"][0]
    lexical_scores = bm25.get_scores(tokenize(query))
    lexical = [docs[i].id for i in sorted(range(len(docs)), key=lambda i: (-lexical_scores[i], docs[i].id))[:settings.retrieve_top_k]]
    by_id = {d.id: d for d in docs}
    fused = rrf([dense, lexical])
    matching = [d for d in docs if d.question_no == question_id]
    fused_ids = {item[0] for item in fused}
    fused.extend((d.id, 0.0) for d in matching if d.id not in fused_ids)
    fused.sort(key=lambda pair: -(pair[1] + (0.03 if by_id[pair[0]].question_no == question_id else 0)))
    candidates = [by_id[doc_id] for doc_id, _ in fused[:20]]
    answer_keys = [d for d in matching if d.kind == "answer_key"]
    if answer_keys and answer_keys[0].id not in {d.id for d in candidates}:
        candidates = candidates[:19] + answer_keys[:1]
    with MODEL_LOCK:
        scores = reranking_model().predict([(query, d.text) for d in candidates], show_progress_bar=False)
    ranked = sorted([Evidence(d.id, d.text, d.kind, d.page, d.question_no, float(score))
                     for d, score in zip(candidates, scores)], key=lambda d: -d.score)
    result = ranked[:settings.rerank_top_n]
    if answer_keys and answer_keys[0].id not in {d.id for d in result}:
        key = next(d for d in ranked if d.id == answer_keys[0].id)
        result = result[:max(0, settings.rerank_top_n - 1)] + [key]
    return result
