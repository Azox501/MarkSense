"""Pure deterministic scoring: no network, database, environment or model calls."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence

from core.schemas import Question, QuestionJudgement, Rubric


def decimal(value: float) -> Decimal:
    """Convert decimal-looking rubric numbers without binary rounding drift."""
    return Decimal(str(value))


def round_question(value: float, maximum: float, step: float) -> float:
    """Cap, round half up once at question level, and cap again."""
    if step <= 0 or maximum <= 0:
        raise ValueError("Question maximum and rounding step must be positive.")
    bounded = max(Decimal(0), min(decimal(value), decimal(maximum)))
    rounded = (bounded / decimal(step)).quantize(Decimal(1), rounding=ROUND_HALF_UP) * decimal(step)
    return float(min(rounded, decimal(maximum)))


@dataclass(frozen=True)
class QuestionScore:
    question_id: str
    criterion_marks: dict[str, float]
    score: float
    maximum: float
    needs_review: bool


@dataclass(frozen=True)
class ExamScore:
    questions: dict[str, float]
    counted_questions: tuple[str, ...]
    penalty: float
    total: float
    percentage: float


def score_question(question: Question, judgement: QuestionJudgement, step: float = 0.5,
                   confidence_threshold: float = 0.7, levels: Mapping[str, float] | None = None) -> QuestionScore:
    """Multiply rubric maxima by levels and round the summed question only."""
    expected = {c.id for c in question.criteria}
    actual = [c.criterion_id for c in judgement.criteria]
    if question.id != judgement.question_id or set(actual) != expected or len(actual) != len(expected):
        raise ValueError("Judgement must contain every expected criterion exactly once.")
    decisions = {c.criterion_id: c for c in judgement.criteria}
    marks = {}
    for criterion in question.criteria:
        level = (levels or {}).get(criterion.id, decisions[criterion.id].level)
        if level not in (0, 0.5, 1):
            raise ValueError("Criterion level must be 0, 0.5 or 1.")
        marks[criterion.id] = float(decimal(criterion.max) * decimal(level))
    raw = float(sum((decimal(v) for v in marks.values()), Decimal(0)))
    return QuestionScore(question.id, marks, round_question(raw, question.max, step), question.max,
                          any(c.confidence < confidence_threshold for c in judgement.criteria))


def score_exam(rubric: Rubric, scores: Mapping[str, float], attempted: Sequence[str],
               wrong_mcq: set[str] | None = None, overrides: Mapping[str, float] | None = None) -> ExamScore:
    """Select optional answers and apply MCQ penalties with a floor per group.

    A teacher score overrides the complete question result, including its penalty.
    For compulsory MCQs the shared question group is all compulsory MCQs.
    """
    attempted_ids = list(dict.fromkeys(attempted))
    values = {}
    overrides = overrides or {}
    for question in rubric.questions:
        value = overrides.get(question.id, scores.get(question.id, 0.0))
        if not decimal(value).is_finite() or not 0 <= value <= question.max:
            raise ValueError(f"{question.id}: score must be between zero and its maximum.")
        values[question.id] = round_question(value, question.max, rubric.rules.round_to)
    counted = [q.id for q in rubric.questions if not q.optional_group]
    for group, rule in rubric.rules.optional_groups.items():
        members = {q.id for q in rubric.questions if q.optional_group == group}
        candidates = [qid for qid in attempted_ids if qid in members]
        if rule.pick == "best":
            candidates.sort(key=lambda qid: -values[qid])
        counted.extend(candidates[:rule.attempt])
    groups: dict[str, list[str]] = {}
    for q in rubric.questions:
        if q.id in counted:
            key = q.optional_group or ("_mcq" if q.type == "mcq" else "_" + q.id)
            groups.setdefault(key, []).append(q.id)
    penalty = Decimal(0)
    total = Decimal(0)
    for members in groups.values():
        subtotal = sum((decimal(values[qid]) for qid in members), Decimal(0))
        wrong = [qid for qid in members if qid in (wrong_mcq or set()) and qid not in overrides
                 and qid in attempted_ids and next(q.type for q in rubric.questions if q.id == qid) == "mcq"]
        deduction = min(subtotal, decimal(rubric.rules.negative_marking.per_wrong) * len(wrong)) if rubric.rules.negative_marking.enabled else Decimal(0)
        penalty += deduction
        total += subtotal - deduction
    return ExamScore(values, tuple(counted), float(penalty), float(total),
                     float(total / decimal(rubric.exam_max) * 100))
