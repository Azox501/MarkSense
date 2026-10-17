import pytest
from pydantic import BaseModel

from core import judge, transcribe
from core.cache import validated_call
from core.config import AppError, get_settings


def test_clients_are_separate(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_API_KEY", "vision-only")
    monkeypatch.setenv("GEMINI_GRADER_API_KEY", "grader-only")
    get_settings.cache_clear()
    judge.grader_client.cache_clear()
    transcribe.vision_client.cache_clear()
    created = []
    def fake(**kwargs):
        value = object()
        created.append((kwargs["api_key"], value))
        return value
    monkeypatch.setattr(judge.genai,"Client",fake)
    assert transcribe.KEY_ENV == "GEMINI_VISION_API_KEY"
    assert judge.KEY_ENV == "GEMINI_GRADER_API_KEY"
    assert transcribe.vision_client() is not judge.grader_client()
    assert [c[0] for c in created] == ["vision-only","grader-only"]
    get_settings.cache_clear()
    judge.grader_client.cache_clear()
    transcribe.vision_client.cache_clear()


def test_invalid_json_retried_once(local_db):
    class Payload(BaseModel):
        value: str
    prompts = []
    def generate(prompt):
        prompts.append(prompt)
        return "not json"
    with pytest.raises(AppError, match="invalid response twice"):
        validated_call("model", "prompt", [], Payload, generate)
    assert len(prompts) == 2
    assert "validation errors" in prompts[1]


def test_transient_attempt_limit(local_db, monkeypatch):
    from core import cache
    class Payload(BaseModel):
        value: str
    class Busy(Exception):
        code = 429
    calls = []
    monkeypatch.setattr(cache.time,"sleep",lambda _: None)
    def generate(prompt):
        calls.append(prompt)
        raise Busy()
    with pytest.raises(AppError):
        validated_call("model","prompt",[],Payload,generate)
    assert len(calls) == 4


def test_numeric_levels_still_strict_after_wire_schema_adapter():
    from pydantic import ValidationError
    from core.schemas import CriterionJudgement
    payload = {"criterion_id":"c1","level":0.25,"remark":"Reason","evidence_quote":"A",
               "source_chunk_id":None,"confidence":0.8}
    with pytest.raises(ValidationError):
        CriterionJudgement.model_validate(payload)
    wire = CriterionJudgement.model_json_schema()["properties"]["level"]
    assert wire["type"] == "number" and "enum" not in wire


def test_draft_rejects_numeric_score_text(local_db, monkeypatch):
    from types import SimpleNamespace
    from test_scoring import rubric_fixture
    monkeypatch.setenv("GEMINI_VISION_API_KEY","vision")
    monkeypatch.setenv("GEMINI_GRADER_API_KEY","grader")
    get_settings.cache_clear()
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='{"question_id":"Q1","hints":["Your score: 3/5"],"concepts_to_revise":[]}')
    monkeypatch.setattr(judge,"grader_client",lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    with pytest.raises(AppError,match="invalid response twice"):
        judge.draft_hints(rubric_fixture().questions[0],"Answer",[])
    assert len(calls) == 2


def test_unretrieved_source_rejected_and_missing_source_lowers_confidence(local_db, monkeypatch):
    import json
    from types import SimpleNamespace
    from test_scoring import rubric_fixture
    monkeypatch.setenv("GEMINI_VISION_API_KEY","vision")
    monkeypatch.setenv("GEMINI_GRADER_API_KEY","grader")
    get_settings.cache_clear()
    question = rubric_fixture().questions[0]
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        source = "made-up" if len(calls) == 1 else None
        payload = {"question_id":"Q1","criteria":[{"criterion_id":c.id,"level":1,"remark":"Reason",
            "evidence_quote":"Answer","source_chunk_id":source,"confidence":0.9} for c in question.criteria],
            "misconception":None,"revision_tip":"Revise notes"}
        return SimpleNamespace(text=json.dumps(payload))
    monkeypatch.setattr(judge,"grader_client",lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    result = judge.judge_question(question,"Answer",[])
    assert len(calls) == 2
    assert all(c.source_chunk_id is None and c.confidence < 0.5 for c in result.criteria)
