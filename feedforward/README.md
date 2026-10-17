# MarkSense

An assessment workspace with separate teacher and student interfaces. AI judges with evidence, Python computes marks, and teachers approve every released score.

## Your workspace

Sign in once using your own account. MarkSense automatically opens the interface for your account role; there is no role switch on the signed-in screen.

- **Teachers:** Overview, Classrooms & assignments, Review & results. Create classrooms, enroll students, add teaching resources and rubrics, review evidence, approve scores and export results.
- **Students:** My workspace, Submit work, My feedback. Join a classroom, work through a draft or final submission, and read private hints and approved feedback.
- **Before sign-in:** only account entry is available. The opposite role's routes are never registered in the session. Page guards and service ownership checks remain in place.

The interface uses a shared local theme, responsive account layout, sidebar identity and navigation, and role-specific overview cards with live counts. Empty workspaces display onboarding guidance. No sample data is automatically created. Existing accounts, work and optional sample fixtures are preserved.

## Setup on Windows

Use Python 3.11 or newer and PowerShell. A fresh clone needs its own API keys and model download. The prepared development environment already has its dependencies, models and local configuration. Live Gemini API validity and the end-to-end API workflow remain unverified.

```powershell
# Only if .venv does not already exist:
uv venv --python 3.11 .venv

uv pip install --python .venv/Scripts/python.exe -r feedforward/requirements.txt
cd feedforward
Copy-Item .env.example .env
```

Manual configuration:

1. Obtain two different Gemini API keys in Google AI Studio. Give one to transcription and the other to grading. Keys in the same Google project may still share quota.
2. Open `feedforward/.env` locally and fill in `GEMINI_VISION_API_KEY` and `GEMINI_GRADER_API_KEY`. Leave `GEMINI_MODEL=gemini-2.5-flash` unless you intend to change it. Do not put keys in chat, source code, screenshots or Git.
3. Install packages and download both BGE models below. Initial installation needs access to PyPI and model hosting. Normal operation loads local model files and disables Chroma/Streamlit usage telemetry; the only application API calls are to Gemini.

```powershell
# From the feedforward folder:
../.venv/Scripts/python.exe scripts/download_models.py
../.venv/Scripts/python.exe scripts/doctor.py
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. Run Streamlit from `feedforward` so it reads `.streamlit/config.toml`. Stop it with Ctrl+C. The server binds to localhost.

Without uv, use `py -3.11 -m venv .venv` and `.venv/Scripts/python.exe -m pip install -r feedforward/requirements.txt` from MarkSense, then follow the same commands.

If installation reports `UnknownIssuer` or `CERTIFICATE_VERIFY_FAILED`, fix the HTTPS trust configuration first. On a managed network, ask your administrator for the approved CA certificate and Python/package-manager configuration. For uv, try `uv --system-certs pip install --python .venv/Scripts/python.exe -r feedforward/requirements.txt` from MarkSense. This option initially failed on the previous connection and later succeeded on the mobile hotspot. Do not disable certificate verification. Retry the ordinary install after trust is fixed, then run `doctor.py`.

`doctor.py` checks package availability, key presence/distinctness and local model files without printing keys or calling any API. It returns a nonzero status when setup is incomplete. It does not verify API quota, key validity or model access.

## Teacher and student workflows

1. Create a teacher account and open **Classrooms & assignments**. Create a classroom, upload your teaching PDFs and create an assignment with validated criteria. Share the classroom code.
2. Students create their own student accounts. In **Submit work**, they join using the code and select an assignment.
3. Students upload a draft for conceptual guidance or a final attempt for assessment. They check and confirm the transcript before processing.
4. Teachers open **Review & results**, inspect source evidence and peer similarity signals, and edit decisions with a reason where necessary. Only explicit approval releases a result.
5. Students open **My feedback** to see draft hints, approved criterion reasons and a revision plan. Teachers download the approved-only CSV/XLSX from their review workspace.

Use separate browser profiles/windows for simultaneous teacher and student sessions on one computer. Gemini receives uploaded page images and assessment prompts; use material you are authorized to process.

## Optional sample fixtures for development

Only run `seed_demo.py` if you want sample data for development. It is not part of normal setup or startup. It creates one teacher, four students, a classroom, a twenty-mark physics exam, three teacher resource PDFs and four submissions. It can be rerun without duplicating the fixtures. The fixture-specific retrieval benchmark is `python scripts/check_retrieval.py` after seeding.

| Account | Email | Password |
| --- | --- | --- |
| Teacher | teacher@demo.test | FeedForwardDemo123! |
| Student | student1@demo.test | FeedForwardDemo123! |
| Student | student2@demo.test | FeedForwardDemo123! |
| Student | student3@demo.test | FeedForwardDemo123! |
| Student | student4@demo.test | FeedForwardDemo123! |

The script prints the classroom join code. All names and work are dummy data. Students 1 and 2 have near-duplicate answers; student 3 has a different answer; student 4 has an image-only, synthetic handwriting-style PDF. On Windows the image fixture uses Segoe Print if installed, with italic print as the portable fallback. It is not a real handwriting accuracy benchmark.

The four seeded submissions have **prefilled fixture transcripts**, not invented Gemini responses or approvals. Sign in as a student, open their pending submission, confirm the transcript and send it for grading. Upload the image-only PDF as a new attempt to exercise real vision transcription.

`python scripts/seed_demo.py --fixtures-only` creates accounts and files without indexing. After model installation, rerun without that option. Resource PDFs are placed in `data/demo`; submission PDFs are in `data/uploads/<classroom>/<assignment>`.

## Optional sample walkthrough

Prepare models, seed data and Gemini quota before the walkthrough. Process one final attempt in advance if API latency would interrupt the demo. Use a normal window for the teacher and a private window or different browser for a student.

1. **0:00–0:30:** Teacher signs in, shows the classroom join code, teacher resources and rubric in Teacher setup.
2. **0:30–1:15:** Student signs in, uploads a demo PDF in Draft mode, confirms OCR and opens conceptual hints in My reports. No marks are released.
3. **1:15–2:15:** Process a Final attempt. Teacher opens the prioritized queue, shows Peer similarity, source pages and criterion reasons. Edit a question with a reason and approve it.
4. **2:15–3:00:** Download the approved-only CSV/XLSX and show the student's approved report, explanations and revision plan. Show the audit history if time permits.

## How it works

`app.py` registers pages with `st.navigation` based on the authenticated account. `core/access.py` handles sign-in and registration, `core/navigation.py` defines disjoint role routes, and `core/dashboard.py` renders their separate landing pages. Each page enforces the account role. Service functions also check teacher ownership, student enrollment and submission ownership.

Teacher PDFs are parsed with PyMuPDF. Scanned pages use the vision client. Approximate 300-token chunks overlap by about 50 tokens, retain question/page/source metadata, and are stored in SQLite and a classroom-specific Chroma collection. Content hashes make uploads idempotent per classroom and resource kind.

Retrieval combines local BGE embeddings and BM25 with reciprocal rank fusion, boosts matching question IDs and reranks up to twenty candidates with the BGE cross encoder. A matching answer-key chunk is retained in the final evidence. BM25 is rebuilt from SQLite on startup and refreshed when chunk IDs change.

Student PDFs are rasterized at 200 dpi and sent to Gemini in batches of at most four pages. The student checks the transcript before processing; original PDFs and correction audits remain available to the teacher. The grading pipeline uses up to three question workers. Local model inference is serialized to avoid concurrent CPU oversubscription.

`transcribe.py` constructs only the vision-key client. `judge.py` constructs a separate grader-key client for criteria and hints. Calls use JSON schemas, temperature zero, a disk cache, four total attempts on transient API errors and one repair attempt after invalid JSON or invalid evidence references. Prompts treat uploaded text as data. Student quotations must be verbatim and source IDs must belong to retrieved evidence; unsupported decisions receive low confidence.

The Gemini SDK's `response_schema` converter rejects numeric enum members. The rubric-level field remains `Literal[0, 0.5, 1]` in Pydantic; its generated wire schema describes a bounded number, with the three permitted values enforced locally on every response. A value such as `0.25` is rejected and triggers the one repair attempt.

`scoring.py` performs all multiplication, question rounding, optional selection, penalties and totals. Draft processing writes hints only. Final processing writes proposed criterion/question results. Only a teacher's explicit approval releases totals to students or exports. Changing an approved result removes approval until it is approved again. Exports use the latest approved final attempt per student, with separate AI/teacher columns and optional per-criterion reasons.

## Scoring conventions

- Round half up at question level, with a cap both before and after rounding. Criteria are never rounded independently.
- `exam_max` must equal the available maximum after optional selection. The short one-question JSON in the supplied brief is illustrative; adjust its `exam_max` or include all exam questions before importing it.
- Optional groups must have questions of equal maximum and one question type. "First" follows the persisted transcript order among nonempty answers. The correction form displays questions in rubric order, so confirmed submissions use that order.
- A wrong MCQ is an attempted MCQ whose criteria all have level zero. Unanswered questions are not penalized. Partial credit is not a wholly wrong MCQ. Each optional MCQ group has a zero floor; compulsory MCQs form one shared group.
- Teacher question overrides include the complete question result. They take precedence over automatic MCQ penalties on that question. A criterion-level edit computes a replacement question score; a later direct score edit supersedes the earlier criterion-level override.
- Carry-forward credit is an instruction to the examiner; the code never guesses whether a conceptual error propagated.
- AI criterion reasons remain visible after a teacher override, accompanied by the teacher's required explanation.

## Local files and privacy

`DATA_DIR` is relative to the project folder unless absolute. SQLite (`app.db`), uploads, Chroma, models and Gemini cache files live beneath it. `.env` and the entire data directory are ignored by Git. Treat all these files as private: the cache contains prompts/results and the database contains transcripts. There is no automatic retention/deletion policy.

This is a local application with email/password accounts and self-selected registration roles. It does not integrate with a school's identity provider or verify teacher affiliation. Page images and text included in prompts are sent to Gemini. The server binds to localhost; public hosting needs a separate deployment and identity configuration.

Peer similarity compares only different students in the same assignment, combining five-word MinHash and embedding cosine. It is a review signal, not a finding of misconduct. Short, formulaic answers can be similar for legitimate reasons. Teachers configure each classroom's threshold and decide how to respond. Students get a first-time warning for a flagged draft without peer names, passages or numeric similarity.

Real-model testing flagged the seeded near-duplicate pair at 0.960 and did not flag unrelated garden/market text. It also flagged the different, incorrect physics answer at 0.814. Shared subject meaning can therefore produce false positives at the default 0.60 threshold; inspect the passages before drawing conclusions.

## Validation and limitations

See `PHASES.md` for the phase-by-phase file list, commands and actual acceptance results. `pytest` includes scoring, authentication, caching, schema/client isolation, transcription batching, chunking, RRF, similarity, pipeline failure atomicity, approval gating, audit and export checks. Tests use fake Gemini/model responses where indicated and do not need paid API calls or downloaded models.

The real-model check is separate: `python scripts/check_retrieval.py`. It measures warm CPU retrieval after an initialization call; the under-five-second target depends on hardware. First load can take longer. The measured warm query took 0.85 seconds outside the execution sandbox. An earlier sandboxed run took 7.76 seconds; do not treat sandbox timing as normal local application performance.

Real OCR, evidence quality and hint quality require live checks with your keys. Structured fields, source membership and quotations are validated; semantic correctness and whether a hint reveals too much still need human evaluation. Resource OCR treats unnumbered scanned material as Q1; explicit question headings improve retrieval. Uploads are limited to 30 MB and 100 unlocked PDF pages. Due dates use the laptop's local clock. Existing students must register before a teacher adds them by email. Rejected work is resubmitted as a new attempt.

Schema tables are created automatically for a fresh local database. No migration framework is included. If you change the schema after creating a database, preserve any needed files and start with a fresh `DATA_DIR`.

API integration follows the [Google Gen AI SDK](https://googleapis.github.io/python-genai/). Persistent vector storage follows the [Chroma Python client documentation](https://docs.trychroma.com/reference/python).
