"""The only place model objects are built; credentials are supplied by settings."""
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from marksense.config.constants import MAX_ATTEMPTS
from marksense.config.settings import get_settings
from marksense.llm.cache import configure_llm_cache


@lru_cache(maxsize=1)
def get_vision_llm() -> ChatGoogleGenerativeAI:
    """Construct an isolated transcription model with the vision credential."""
    settings = get_settings()
    settings.require_credentials()
    configure_llm_cache()
    return ChatGoogleGenerativeAI(model=settings.model, google_api_key=settings.vision_api_key,
                                 temperature=0, max_retries=MAX_ATTEMPTS - 1, timeout=120, cache=True)


@lru_cache(maxsize=1)
def get_grader_llm() -> ChatGoogleGenerativeAI:
    """Construct an isolated grading model with the grader credential."""
    settings = get_settings()
    settings.require_credentials()
    configure_llm_cache()
    return ChatGoogleGenerativeAI(model=settings.model, google_api_key=settings.grader_api_key,
                                 temperature=0, max_retries=MAX_ATTEMPTS - 1, timeout=120, cache=True)
