# MarkSense

A local diagnostic grading co-pilot for teachers. AI judges rubric criteria with evidence, Python computes marks, and teachers approve every released score.

The application source is in [`feedforward/`](feedforward/). It includes a multi-page Streamlit interface, SQLite storage, local hybrid retrieval, peer similarity review, separate Gemini transcription and grading clients, and approved-only reports and exports.

See the [setup guide and demo walkthrough](feedforward/README.md) and the [phase-by-phase validation log](feedforward/PHASES.md).

## Quick start on Windows

From the repository root, using Python 3.11+ and uv:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r feedforward/requirements.txt
cd feedforward
Copy-Item .env.example .env
# Edit .env locally and enter two distinct Gemini API keys.
../.venv/Scripts/python.exe scripts/download_models.py
../.venv/Scripts/python.exe scripts/seed_demo.py
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. Use dummy data only. Keep API keys, uploads, model files, databases and caches out of Git.
