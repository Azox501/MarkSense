"""Download both models once; normal app execution only loads local files."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from sentence_transformers import CrossEncoder, SentenceTransformer
from core.config import EMBED_MODEL, RERANK_MODEL, get_settings


def main() -> None:
    """Download model snapshots into the project data directory."""
    target = get_settings(False).data_dir / "models"
    target.mkdir(parents=True, exist_ok=True)
    SentenceTransformer(EMBED_MODEL, device="cpu").save(str(target / "embed"))
    CrossEncoder(RERANK_MODEL, device="cpu").save(str(target / "rerank"))
    print(f"Models ready: {target}")


if __name__ == "__main__":
    main()
