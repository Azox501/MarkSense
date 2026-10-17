import pytest
from pydantic import BaseModel

from core.cache import validated_call
from core.config import AppError, get_settings


def test_missing_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_API_KEY", "")
    monkeypatch.setenv("GEMINI_GRADER_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(AppError, match="GEMINI_VISION_API_KEY.*GEMINI_GRADER_API_KEY"):
        get_settings()
    get_settings.cache_clear()


def test_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    class Result(BaseModel):
        text: str
    calls = []
    def generate(prompt):
        calls.append(prompt)
        return '{"text":"cached"}'
    for _ in range(2):
        assert validated_call("model", "prompt", [b"image"], Result, generate).text == "cached"
    assert len(calls) == 1
    get_settings.cache_clear()
