"""Read-only setup checks; never print keys or contact external services."""
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """Report missing packages, credentials and model snapshots."""
    checks = {"streamlit":"streamlit", "sqlalchemy":"sqlalchemy", "bcrypt":"bcrypt", "fitz":"PyMuPDF",
              "chromadb":"chromadb", "rank_bm25":"rank-bm25", "sentence_transformers":"sentence-transformers",
              "google.genai":"google-genai", "pydantic":"pydantic", "datasketch":"datasketch",
              "pandas":"pandas", "openpyxl":"openpyxl", "diskcache":"diskcache", "dotenv":"python-dotenv", "pytest":"pytest"}
    failed = False
    print("Python:", sys.version.split()[0])
    for module, package in checks.items():
        try:
            present = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            present = False
        print(("PASS " if present else "MISSING ") + package)
        failed |= not present
    if importlib.util.find_spec("dotenv"):
        from core.config import AppError, get_settings
        try:
            get_settings()
            print("PASS two distinct Gemini keys configured (values hidden)")
        except AppError as exc:
            print("SETUP " + str(exc))
            failed = True
        for name in ("embed", "rerank"):
            present = (get_settings(False).data_dir / "models" / name / "config.json").exists()
            print(("PASS " if present else "MISSING ") + "local model " + name)
            failed |= not present
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
