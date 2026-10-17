"""Layering, key-boundary and client-isolation acceptance checks."""
import ast
from pathlib import Path
import pytest
from marksense.config.settings import ROOT, Settings


def test_environment_reads_only_in_settings():
    for path in [*(ROOT / "marksense").rglob("*.py"), *(ROOT / "app").rglob("*.py")]:
        if path == ROOT / "marksense/config/settings.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "os.getenv" not in text and "os.environ" not in text, path
        assert "GEMINI_VISION_API_KEY" not in text and "GEMINI_GRADER_API_KEY" not in text, path


def test_import_boundaries():
    forbidden_ui = {"db", "llm", "ingestion", "retrieval", "judging", "scoring", "config", "transcription", "reporting", "integrity"}
    for path in [*(ROOT / "marksense").rglob("*.py"), *(ROOT / "app").rglob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if path.is_relative_to(ROOT / "app") and module.startswith("marksense."):
                assert module.split(".")[1] not in forbidden_ui, (path, module)
            if module == "marksense.llm.clients":
                for name in node.names:
                    if name.name == "get_vision_llm":
                        assert path.is_relative_to(ROOT / "marksense/transcription"), path
                    if name.name == "get_grader_llm":
                        assert any(path.is_relative_to(ROOT / "marksense" / folder) for folder in ("judging", "services")), path
            if path.is_relative_to(ROOT / "marksense"):
                assert not module.startswith("app"), path
                if not path.is_relative_to(ROOT / "marksense/services"):
                    assert not module.startswith("marksense.services"), path
                if path.parent.name in {"scoring", "integrity"}:
                    assert not module.startswith(("langchain", "marksense.db")), path


def test_settings_reject_missing_or_shared_keys(tmp_path):
    with pytest.raises(Exception):
        Settings(_env_file=None, vision_api_key="", grader_api_key="").require_credentials()
    with pytest.raises(Exception):
        Settings(_env_file=None, vision_api_key="same", grader_api_key="same").require_credentials()


def test_two_distinct_model_objects(tmp_path, monkeypatch):
    from marksense.llm import clients
    settings = Settings(_env_file=None, vision_api_key="vision-only", grader_api_key="grader-only", data_dir=tmp_path)
    monkeypatch.setattr(clients, "get_settings", lambda: settings)
    monkeypatch.setattr(clients, "configure_llm_cache", lambda: None)
    captured = []
    def build(**kwargs):
        captured.append(kwargs)
        return object()
    monkeypatch.setattr(clients, "ChatGoogleGenerativeAI", build)
    clients.get_vision_llm.cache_clear()
    clients.get_grader_llm.cache_clear()
    assert clients.get_vision_llm() is not clients.get_grader_llm()
    assert captured[0]["google_api_key"].get_secret_value() == "vision-only"
    assert captured[1]["google_api_key"].get_secret_value() == "grader-only"
    assert all(c["temperature"] == 0 and c["cache"] for c in captured)
    clients.get_vision_llm.cache_clear()
    clients.get_grader_llm.cache_clear()
