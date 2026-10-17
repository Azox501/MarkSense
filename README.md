# MarkSense

A local assessment workspace with separate teacher and student interfaces. AI judges rubric criteria with evidence, Python computes marks, and teachers approve every released score.

The application source is in [`feedforward/`](feedforward/). It includes a multi-page Streamlit interface, SQLite storage, local hybrid retrieval, peer similarity review, separate Gemini transcription and grading clients, and approved-only reports and exports.

See the [setup guide and teacher/student workflows](feedforward/README.md) and the [phase-by-phase validation log](feedforward/PHASES.md).

## Quick start on Windows

From the repository root, using Python 3.11+ and uv:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r feedforward/requirements.txt
cd feedforward
Copy-Item .env.example .env
# Edit .env locally and enter two distinct Gemini API keys.
../.venv/Scripts/python.exe scripts/download_models.py
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501` and create your account. Teachers get an overview, classrooms and assignments, and review/results tools. Students get their own workspace, submission tools, and private feedback. Navigation is registered only for the signed-in role; a student session never registers teacher pages.

Fresh workspaces start empty. Sample fixtures are optional and are never loaded automatically. Keep API keys, uploads, model files, databases and caches out of Git. Uploaded pages and assessment prompts are sent to Gemini.
