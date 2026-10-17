# MarkSense workspace instructions

- The canonical GitHub repository is `https://github.com/Azox501/MarkSense`; use it as `origin`.
- The user has requested that completed updates to this project be committed and pushed to this repository henceforth. After appropriate validation, commit the intended code/documentation changes and push the current working branch unless the user explicitly asks otherwise. Report the commit/branch and any push failure accurately.
- Use the `codex/` prefix for newly created branches. Do not force-push, overwrite remote history, or publish unrelated local work.
- Application source is under `feedforward/`. Run commands from that directory when they depend on Streamlit's project configuration or local imports.
- Never commit actual credentials, `.env` files, Streamlit secrets, local uploads, downloaded models, SQLite/Chroma databases, or Gemini caches. `.env.example` must contain placeholders only. Do not print real key values in command output.
- Preserve separate Gemini vision/grading clients and Python-only marks calculation. Final scores require explicit teacher approval.
- Keep teacher/student interfaces separate with account-scoped `st.navigation` routes. Do not restore automatic mixed-role page discovery or a permanent demo banner. Sample fixtures are optional development tools; preserve existing user data when changing presentation.
- Validate changes with checks appropriate to their scope. The core suite is `../.venv/Scripts/python.exe -m pytest -q` from `feedforward/`. Real-model retrieval is checked separately with `scripts/check_retrieval.py`.
- The user most recently requested local tests only. Do not make live Gemini calls unless they subsequently authorize API testing or invoke the app's processing flow themselves.
