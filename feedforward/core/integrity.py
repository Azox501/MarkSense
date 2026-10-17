"""Peer similarity signals: lexical MinHash and local embedding cosine."""
from dataclasses import dataclass
import re
from typing import Callable

from datasketch import MinHash
import numpy as np
from sqlalchemy import delete, select

from core.config import AppError
from core.db import Classroom, IntegrityReport, Submission, session_scope
from core.models import embed
from core.schemas import Transcript


@dataclass(frozen=True)
class PeerMatch:
    submission_id: int
    similarity: float
    passages: list[dict[str, str]]


def shingles(text: str) -> set[str]:
    """Produce five-word shingles, avoiding false overlap for empty answers."""
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + 5]) for i in range(len(words) - 4)}


def lexical_similarity(left: str, right: str) -> float:
    """Approximate lexical overlap using deterministic 128-permutation MinHash."""
    a, b = shingles(left), shingles(right)
    if not a or not b:
        return 0.0
    hashes = [MinHash(num_perm=128, seed=42), MinHash(num_perm=128, seed=42)]
    for target, values in zip(hashes, [a, b]):
        for value in sorted(values):
            target.update(value.encode())
    return float(hashes[0].jaccard(hashes[1]))


def cosine(left: list[float], right: list[float]) -> float:
    """Return bounded cosine, including safe handling of zero vectors."""
    a, b = np.asarray(left), np.asarray(right)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return max(0.0, min(1.0, float(a @ b) / denominator)) if denominator else 0.0


def flagged_passages(left: str, right: str, encoder: Callable = embed) -> list[dict[str, str]]:
    """Show the strongest lexical/semantic sentence pairs for teacher inspection."""
    split = lambda text: [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()][:30]
    aa, bb = split(left), split(right)
    if not aa or not bb:
        return []
    vectors = encoder(aa + bb)
    candidates = [(max(lexical_similarity(a, b), cosine(vectors[i], vectors[len(aa) + j])), i, j)
                  for i, a in enumerate(aa) for j, b in enumerate(bb)]
    candidates.sort(reverse=True)
    pairs, seen = [], set()
    for _, i, j in candidates:
        if i not in seen:
            pairs.append({"student": aa[i], "peer": bb[j]})
            seen.add(i)
        if len(pairs) == 3:
            break
    return pairs


def compare_peers(text: str, peers: list[tuple[int, str]], threshold: float,
                  encoder: Callable = embed) -> list[PeerMatch]:
    """Compare supplied peer texts; callers enforce assignment membership."""
    if not text.strip() or not peers:
        return []
    peers = [(identifier, value) for identifier, value in peers if value.strip()]
    if not peers:
        return []
    vectors = encoder([text] + [value for _, value in peers])
    matches = []
    for index, (identifier, value) in enumerate(peers, 1):
        score = max(lexical_similarity(text, value), cosine(vectors[0], vectors[index]))
        if score >= threshold:
            matches.append(PeerMatch(identifier, score, flagged_passages(text, value, encoder)))
    return sorted(matches, key=lambda m: -m.similarity)


def transcript_text(submission: Submission) -> str:
    """Flatten answer text without adding question labels to similarity input."""
    if not submission.transcript_json:
        return ""
    return "\n".join(a.text for a in Transcript.model_validate(submission.transcript_json).answers)


def check_submission(submission_id: int, classroom_id: int) -> list[PeerMatch]:
    """Compare only different students in this same assignment and classroom."""
    from core.db import Assignment
    with session_scope() as session:
        submission = session.get(Submission, submission_id)
        assignment = session.get(Assignment, submission.assignment_id) if submission else None
        classroom = session.get(Classroom, classroom_id)
        if not assignment or assignment.classroom_id != classroom_id or not classroom:
            raise AppError("Cannot compare peers outside this classroom.")
        peers = list(session.scalars(select(Submission).where(
            Submission.assignment_id == submission.assignment_id, Submission.student_id != submission.student_id,
            Submission.transcript_json.is_not(None), Submission.status != "rejected")))
        text = transcript_text(submission)
        peer_texts = [(p.id, transcript_text(p)) for p in peers]
        threshold = classroom.similarity_threshold
    matches = compare_peers(text, peer_texts, threshold)
    with session_scope() as session:
        session.execute(delete(IntegrityReport).where(IntegrityReport.submission_id == submission_id))
        for match in matches:
            session.add(IntegrityReport(submission_id=submission_id, matched_submission_id=match.submission_id,
                                        similarity=match.similarity, flagged_passages_json=match.passages))
    return matches
