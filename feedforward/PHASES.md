# Build and acceptance log

Acceptance results distinguish implementation checks from live checks. No Gemini call is fabricated.

## Current status — 2026-10-17, after hotspot setup

The phase entries below retain the original build history. This section supersedes their earlier installation/test blockers.

- PASS: installed all 132 resolved packages in the Python 3.13.2 virtual environment, using system certificates on the mobile hotspot.
- PASS: downloaded and saved both BGE models locally.
- PASS: seeded demo accounts, PDFs, classroom and exam; indexed all teacher resources in SQLite and Chroma.
- PASS: all 27 pytest tests, 15.04 seconds outside the sandbox. Initial sandbox run had 16 passes and 11 temporary-directory permission errors; those were environment errors and disappeared outside the sandbox.
- PASS: real-model retrieval returned related evidence in the top three, with a warm CPU query of 0.85 seconds outside the sandbox. The earlier sandboxed run took 7.76 seconds.
- PASS: Streamlit startup with blank keys shows a clear setup error without an unhandled exception.
- PASS: local UI smoke tests for teacher/student login, Teacher setup, empty Teacher review/export, Student submit/transcript preview, Student reports, and student denial from Teacher review. These checks used process-local placeholder keys and made no Gemini calls.
- PASS: real-model similarity flagged the seeded near-duplicate pair at 0.960 with three passage pairs; unrelated garden/market text was not flagged at the default 0.60 threshold.
- OBSERVED LIMITATION: the different, incorrect physics answer was also flagged at 0.814 because embeddings capture shared subject meaning. This is not evidence of copying; teacher review is required. No automatic sanction or threshold change was applied.
- PASS: two distinct Gemini keys are configured in the local, Git-ignored `.env`; setup checks pass. No credential values are included in this repository. Their validity with Gemini remains unverified.
- NOT RUN: live vision transcription, Gemini grading/hints, and the complete live approval workflow. The user requested local tests only; no Gemini calls were made.

## Phase 0 — scaffold and configuration

Files: `requirements.txt`, `.env.example`, `core/config.py`, `core/cache.py`, `scripts/download_models.py`, README and configuration/cache tests.

Run: install requirements; `python scripts/download_models.py`; `python -m pytest tests/test_config_cache.py`.

Environment: Python 3.13.2 virtual environment created. Dependency installation blocked by `UnknownIssuer` TLS certificate errors for PyPI; model download pending. Missing-key and cache tests implemented; execution pending dependency installation.

## Phase 1 — database, accounts and classrooms

Files: `core/db.py`, `core/auth.py`, `core/ui.py`, `app.py`, authentication tests.

Run: `python -m streamlit run app.py`; `python -m pytest tests/test_auth.py`.

Acceptance: bcrypt hashing, role rejection, join-code validation and enrollment tests implemented. Execution pending dependency installation. Additional persistent fields support classroom thresholds, original AI decisions, teacher overrides, hints and approval totals.

## Phase 2 — resource ingestion and rubrics

Files: `core/ingest.py`, `core/models.py`, `core/schemas.py`, `pages/1_Teacher_Setup.py`, ingestion tests.

Run: Teacher setup page; `python -m pytest tests/test_ingest.py`.

Acceptance: Python compilation, Pydantic schema import and all 11 SQLAlchemy table mappings pass with installed system packages. PDF corruption, chunk boundaries and invalid-rubric tests provided. Model-backed indexing pending packages/models. Content hashes plus database uniqueness prevent duplicate resource/chunk creation. Scanned-page ingestion uses the Phase 4 transcriber when it becomes available.

## Phase 3 — hybrid retrieval

Files: `core/retrieval.py`, `tests/test_retrieval.py`, `scripts/check_retrieval.py`; startup BM25 initialization in `app.py`.

Run: `python -m pytest tests/test_retrieval.py`; after seeding, `python scripts/check_retrieval.py`.

Acceptance: RRF hand-ranked ordering and duplicate tests supplied. Real-model top-three relevance and warm CPU latency checks pending model installation. The <5s target is hardware-dependent and not claimed as measured. A matching answer-key chunk is retained after reranking.

## Phase 4 — submission and transcription

Files: `core/transcribe.py`, `core/submissions.py`, `pages/2_Student_Submit.py`, transcription tests.

Run: Student submit page; `python -m pytest tests/test_transcribe.py`.

Acceptance: batched 200-dpi rendering, continuation merging, illegibility retention and cache integration implemented. The student must confirm an editable transcript; changes are audited. Real typed/handwritten Gemini calls pending keys and environment setup. A mocked batch-merging test is supplied and is not a claim of real OCR accuracy.

## Phase 5 — peer similarity

Files: `core/integrity.py`, `tests/test_integrity.py`; configurable classroom threshold in Teacher setup.

Run: `python -m pytest tests/test_integrity.py`; pipeline integration follows in Phase 6.

Acceptance: deterministic MinHash, cosine, maximum-of-two combination, sentence pairs and same-assignment SQL scoping implemented. Near-duplicate/unrelated tests use controlled embedding vectors; real BGE similarity acceptance pending model setup. Signals are labeled Peer similarity and never claim AI-text detection.

## Phase 6 — grading, deterministic scoring and draft hints

Files: `core/judge.py`, `core/scoring.py`, `core/pipeline.py`, scoring and Gemini-contract tests.

Run: `python -m pytest tests/test_scoring.py tests/test_judge.py`; submit a confirmed transcript.

Acceptance: worked-example, cap, half-up question rounding, optional groups, MCQ group floors, confidence and override tests provided. Client isolation, four-attempt transient retry and one schema-repair retry tests provided. Drafts persist only DraftHint objects; final question/criterion writes are transactional. Three workers maximum; CPU inference is serialized to avoid oversubscription. Live grading/hint quality pending Gemini credentials.

## Phase 7 — teacher review and exports

Files: `core/review.py`, `core/export.py`, `pages/3_Teacher_Review.py`.

Run: Teacher review page; review/export service tests in the final suite.

Acceptance: prioritized queue, source/page snapshots, PDF download, audited score/level edits with reasons, approval, rejection and approved-only CSV/XLSX implemented. AI scores remain immutable. Reapproval calls the pure scoring engine. Unedited teacher scores remain nullable internally to preserve MCQ penalties; exports show the effective teacher value. Execution of export checks pending pandas/openpyxl installation.

## Phase 8 — student reports, demo data and documentation

Files: `core/reports.py`, `pages/4_Student_Report.py`, `scripts/seed_demo.py`, `scripts/doctor.py`, `.streamlit/config.toml`, expanded README, report/review/export and pipeline tests.

Run: `python scripts/seed_demo.py`; `python scripts/doctor.py`; `python -m pytest -q`; `python -m streamlit run app.py`.

Acceptance: approval-gated student report, hints history, per-criterion reasons, misconceptions, revision plan and idempotent demo fixtures implemented. Streamlit telemetry disabled and localhost binding configured. Full UI flow, real OCR/LLM output, model download and exports remain unverified because dependencies/models/keys are unavailable. This is implementation-complete, not acceptance-complete.

## Verification actually executed

- PASS: `python -m compileall -q feedforward` for every Python file.
- PASS: local import-path checks and parsing for 39 Python files; all core functions have argument and return annotations.
- PASS: all 11 SQLAlchemy models map and all 11 tables create in an in-memory SQLite database.
- PASS: worked example from criterion multiplication through total: Q1=4, Q2=3.5, Q3=6, total=13.5/20, percentage=67.5%.
- PASS: direct assertions for low-confidence flags, half-up rounding, both caps, MCQ-only negative marking, group floors, teacher override and optional best/first selection.
- PASS: invalid rubric rejection and explicit fail-fast errors naming both missing Gemini variables.
- PASS: installed Gemini SDK converts QuestionJudgement, DraftHint and Transcript schemas. Numeric-literal SDK incompatibility found and adapted; local level 0.25 rejection verified.
- BLOCKED: full dependency installation: PyPI `invalid peer certificate: UnknownIssuer`. Retried with Windows/system trust; same error. Offline package cache lacks pytest. No TLS verification bypass used.
- BLOCKED: `../.venv/Scripts/python.exe -m pytest -q`: `No module named pytest` (environment failure, not a passing test run).
- PROVIDED: 27 pytest tests across 10 test modules, including duplicate ingestion, score-free drafts, source-ID validation, isolation, approval/reapproval, exports and pipeline failure atomicity. These are written, not executed.
- BLOCKED: actual missing-key/cache/auth/transcription/retrieval/integrity/review/export pytest suites until dependencies install. Direct key/scoring/schema checks above do not imply these suites passed.
- PENDING MANUAL SETUP: two distinct Gemini keys in `.env`; no keys requested in chat or invented.
- PENDING: both downloaded BGE models, real retrieval relevance/latency, typed/handwritten OCR, live grading/hints and complete two-browser flow.

Next steps: fix machine/network certificate trust, install requirements, configure `.env`, download models, run seed/tests/benchmark, launch the app. README contains exact commands and the three-minute walkthrough.
