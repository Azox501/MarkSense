"""Validated rubric and Gemini contracts; model outputs never contain marks."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Criterion(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    max: float = Field(gt=0)
    description: str = Field(min_length=1)


class Question(StrictModel):
    id: str = Field(pattern=r"^Q[1-9][0-9]*$")
    text: str = ""
    max: float = Field(gt=0)
    type: Literal["descriptive", "mcq"] = "descriptive"
    optional_group: str | None = None
    criteria: list[Criterion] = Field(min_length=1)


class OptionalGroup(StrictModel):
    attempt: int = Field(gt=0)
    pick: Literal["best", "first"] = "best"


class NegativeMarking(StrictModel):
    enabled: bool = False
    per_wrong: float = Field(default=0.25, ge=0)
    applies_to: Literal["mcq"] = "mcq"


class Rules(StrictModel):
    carry_forward: bool = True
    optional_groups: dict[str, OptionalGroup] = Field(default_factory=dict)
    negative_marking: NegativeMarking = Field(default_factory=NegativeMarking)
    round_to: float = Field(default=0.5, gt=0)


class Rubric(StrictModel):
    exam_max: float = Field(gt=0)
    questions: list[Question] = Field(min_length=1)
    rules: Rules = Field(default_factory=Rules)

    @model_validator(mode="after")
    def consistent(self) -> "Rubric":
        ids = [q.id for q in self.questions]
        criterion_ids = [c.id for q in self.questions for c in q.criteria]
        if len(ids) != len(set(ids)) or len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("Question and criterion IDs must be unique.")
        for q in self.questions:
            if q.optional_group and q.optional_group not in self.rules.optional_groups:
                raise ValueError(f"{q.id}: optional group {q.optional_group} is not defined.")
        for group, rule in self.rules.optional_groups.items():
            members = [q for q in self.questions if q.optional_group == group]
            if members and rule.attempt > len(members):
                raise ValueError(f"{group}: attempt count exceeds available questions.")
            if members and len({q.type for q in members}) > 1:
                raise ValueError("An optional group must contain only one question type.")
            if members and len({q.max for q in members}) > 1:
                raise ValueError("Questions in an optional group must have equal maximum marks.")
        capacity = sum(q.max for q in self.questions if not q.optional_group)
        capacity += sum(rule.attempt * next(q.max for q in self.questions if q.optional_group == group)
                        for group, rule in self.rules.optional_groups.items()
                        if any(q.optional_group == group for q in self.questions))
        if abs(self.exam_max - capacity) > 1e-9:
            raise ValueError("exam_max must equal the marks available after optional-question selection.")
        return self


def _numeric_level_schema(schema: dict[str, Any]) -> None:
    """Adapt numeric Literals to Gemini's wire schema; local validation stays exact.

    google-genai's response_schema converter accepts string enums only. Describe
    a bounded number on the wire, then enforce the three permitted values locally.
    """
    schema.pop("enum", None)
    schema.update(type="number", minimum=0, maximum=1,
                  description="Only 0, 0.5 or 1 is valid. Never return marks.")


class CriterionJudgement(StrictModel):
    criterion_id: str
    level: Literal[0, 0.5, 1] = Field(json_schema_extra=_numeric_level_schema)
    remark: str = Field(min_length=1)
    evidence_quote: str
    source_chunk_id: str | None
    confidence: float = Field(ge=0, le=1)


class QuestionJudgement(StrictModel):
    question_id: str
    criteria: list[CriterionJudgement] = Field(min_length=1)
    misconception: str | None
    revision_tip: str = Field(min_length=1)


class DraftHint(StrictModel):
    question_id: str
    hints: list[str] = Field(min_length=1)
    concepts_to_revise: list[str]


class TranscribedAnswer(StrictModel):
    question_id: str = Field(pattern=r"^Q[1-9][0-9]*$")
    text: str
    legibility: float = Field(ge=0, le=1)


class Transcript(StrictModel):
    answers: list[TranscribedAnswer]

    @model_validator(mode="after")
    def unique_questions(self) -> "Transcript":
        ids = [a.question_id for a in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Merge duplicate question IDs into a single answer.")
        return self
