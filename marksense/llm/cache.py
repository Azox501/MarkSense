"""LangChain SQLite response cache and bounded structured-output repair."""
from collections.abc import Callable
import hashlib
import json
from threading import Lock
from typing import Any, TypeVar

from diskcache import Cache
from langchain_community.cache import SQLiteCache
from langchain_core.exceptions import OutputParserException
from langchain_core.globals import set_llm_cache
from pydantic import BaseModel, ValidationError
from marksense.config.settings import AppError, get_settings

T = TypeVar("T", bound=BaseModel)
_cache_lock = Lock()
_configured_path: str | None = None


def configure_llm_cache() -> None:
    """Enable persistent LangChain caching without an external cache service."""
    global _configured_path
    directory = get_settings().data_dir / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    path = str(directory / "llm_cache.db")
    with _cache_lock:
        if _configured_path != path:
            set_llm_cache(SQLiteCache(database_path=path))
            _configured_path = path


def page_cache_key(model: str, prompt: str, image: bytes, schema: type[BaseModel]) -> str:
    """Hash model, prompt, page bytes and schema, never credentials."""
    payload = [model, prompt, hashlib.sha256(image).hexdigest(), schema.model_json_schema()]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def page_cache() -> Cache:
    """Open the disk cache for validated page transcription results."""
    return Cache(str(get_settings().data_dir / "cache/pages"))


def structured_invoke(chain: Any, values: dict[str, Any], schema: type[T],
                      validate: Callable[[T], T] | None = None) -> T:
    """Repair a parsing/grounding failure once; let the model bound transport retries."""
    current = dict(values, repair="")
    for attempt in range(2):
        try:
            raw = chain.invoke(current)
            result = raw if isinstance(raw, schema) else schema.model_validate(raw)
            return validate(result) if validate else result
        except (ValidationError, OutputParserException, ValueError) as exc:
            if attempt:
                raise AppError("The model returned an invalid structured response twice. Please retry.") from exc
            current["repair"] = "Repair the previous validation failure, using the same evidence: " + str(exc)[:1200]
        except Exception as exc:
            raise AppError("Gemini could not complete the request. Check your connection, key access and quota, then retry.") from exc
    raise AppError("No valid model response was returned.")
