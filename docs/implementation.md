# LangChain migration acceptance log

The migration follows the supplied phases in order. Gemini tests are mocked unless explicitly marked live. No live Gemini calls are authorized for this migration.

## Phase 0 — skeleton, settings and dependency verification

Created the root package/layout and central pydantic-settings boundary. Existing local credentials were copied into a Git-ignored root `.env`, without displaying them. The old application and data are retained until cutover.

The first dependency installation hit locked files, so the migration uses an isolated `.venv-langchain`. OneDrive rejected hardlinks; installation was retried with `--link-mode copy`.

Acceptance pending: verified imports, pinned dependencies, editable installation, configuration/client/cache and import-boundary tests.
