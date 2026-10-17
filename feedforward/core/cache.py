"""Disk caching and bounded retries shared by two isolated Gemini clients."""
from collections.abc import Callable
import hashlib
import json
import random
import time
from typing import Any, TypeVar

from diskcache import Cache
from pydantic import BaseModel, ValidationError

from core.config import AppError, get_settings

T = TypeVar("T", bound=BaseModel)


def cache_key(model: str, prompt: str, images: list[bytes], schema: dict[str, Any]) -> str:
    """Hash all request inputs without storing credentials."""
    payload = [model, prompt, [hashlib.sha256(i).hexdigest() for i in images], schema]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validated_call(model: str, prompt: str, images: list[bytes], schema: type[T],
                   generate: Callable[[str], str], validate: Callable[[T], T] | None = None) -> T:
    """Cache valid responses; retry transient errors four times and invalid JSON once."""
    with Cache(str(get_settings(False).data_dir / "cache")) as cache:
        current = prompt
        original_key = cache_key(model, prompt, images, schema.model_json_schema())
        for validation_attempt in range(2):
            key = cache_key(model, current, images, schema.model_json_schema())
            raw = cache.get(key)
            if raw is None:
                for attempt in range(4):
                    try:
                        raw = generate(current)
                        break
                    except Exception as exc:
                        code = getattr(exc, "code", getattr(exc, "status_code", None))
                        transient = str(code) == "429" or str(code).startswith("5")
                        if not transient or attempt == 3:
                            raise AppError("Gemini could not complete this request. Check your keys, quota and connection, then retry.") from exc
                        time.sleep(2 ** attempt + random.uniform(0, 0.25))
            try:
                result = schema.model_validate_json(raw)
                if validate:
                    result = validate(result)
            except (ValidationError, ValueError) as exc:
                cache.delete(key)
                if validation_attempt:
                    raise AppError("Gemini returned an invalid response twice. Please retry this submission.") from exc
                current = prompt + "\nCorrect the previous validation errors and return JSON only: " + str(exc)
                continue
            cache.set(key, raw)
            cache.set(original_key, raw)
            return result
    raise AppError("No valid Gemini response was received.")
