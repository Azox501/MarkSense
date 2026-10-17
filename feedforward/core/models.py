"""Lazy, CPU-only local model loading; never download during app execution."""
import os
from functools import lru_cache
from threading import RLock
from typing import Any

from core.config import AppError, get_settings

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
MODEL_LOCK = RLock()


@lru_cache(maxsize=1)
def embedding_model() -> Any:
    """Load the pre-downloaded BGE embedding model."""
    path = get_settings(False).data_dir / "models" / "embed"
    if not path.exists():
        raise AppError("Local embedding model is missing. Run python scripts/download_models.py first.")
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(str(path), device="cpu", local_files_only=True)


@lru_cache(maxsize=1)
def reranking_model() -> Any:
    """Load the pre-downloaded cross encoder."""
    path = get_settings(False).data_dir / "models" / "rerank"
    if not path.exists():
        raise AppError("Local reranker is missing. Run python scripts/download_models.py first.")
    from sentence_transformers import CrossEncoder
    return CrossEncoder(str(path), device="cpu", local_files_only=True, max_length=512)


def embed(texts: list[str], query: bool = False) -> list[list[float]]:
    """Encode with normalized vectors; serialize CPU inference across workers."""
    if not texts:
        return []
    inputs = ["Represent this sentence for searching relevant passages: " + t for t in texts] if query else texts
    with MODEL_LOCK:
        return embedding_model().encode(inputs, normalize_embeddings=True, show_progress_bar=False).tolist()
