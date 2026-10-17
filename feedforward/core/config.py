"""Environment configuration; importing this module never requires credentials."""
from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"


class AppError(Exception):
    """A safe, actionable error to display to a user."""


@dataclass(frozen=True)
class Settings:
    vision_key: str
    grader_key: str
    model: str
    data_dir: Path
    similarity_threshold: float
    confidence_threshold: float
    retrieve_top_k: int
    rerank_top_n: int


@lru_cache(maxsize=2)
def get_settings(require_keys: bool = True) -> Settings:
    """Load settings, failing clearly at app startup when a key is absent."""
    load_dotenv(ROOT / ".env", override=False)
    vision = os.getenv("GEMINI_VISION_API_KEY", "").strip()
    grader = os.getenv("GEMINI_GRADER_API_KEY", "").strip()
    if require_keys:
        missing = [name for name, value in (("GEMINI_VISION_API_KEY", vision),
                   ("GEMINI_GRADER_API_KEY", grader)) if not value]
        if missing:
            raise AppError("Set " + " and ".join(missing) + " in feedforward/.env, then restart Streamlit.")
        if vision == grader:
            raise AppError("Use two different API keys for vision and grading.")
    try:
        similarity = float(os.getenv("SIMILARITY_THRESHOLD", "0.60"))
        confidence = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
        top_k = int(os.getenv("RETRIEVE_TOP_K", "20"))
        top_n = int(os.getenv("RERANK_TOP_N", "5"))
        if not (0 <= similarity <= 1 and 0 <= confidence <= 1 and top_k > 0 and top_n > 0):
            raise ValueError
    except ValueError as exc:
        raise AppError("Thresholds must be between 0 and 1; retrieval limits must be positive integers.") from exc
    directory = Path(os.getenv("DATA_DIR", "data"))
    if not directory.is_absolute():
        directory = ROOT / directory
    return Settings(vision, grader, os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    directory.resolve(), similarity, confidence, top_k, top_n)
