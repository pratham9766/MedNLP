# MedNLP Insight

MedNLP Insight is an informational research prototype for evidence-linked analysis of synthetic or user-provided medical reports. It is not a diagnostic system or a substitute for professional medical judgment. Do not use it for emergency or treatment decisions.

## Current status

The implementation provides a FastAPI service, local SQLite persistence, PBKDF2 password hashing and signed bearer-token authentication, per-user document ownership, private file storage, PDF/image text extraction, deterministic report classification and extraction, evidence citations, report-scoped extractive question answering, persistent review annotations with an original-value audit trail, JSON export, and a React/TypeScript UI. The UI includes correction editing, report type/status filters, page text navigation, and review statuses. Processing currently runs in a local background thread; this is suitable only for development. Production PostgreSQL migrations and persistent job workers remain deployment work and are described in `docs/limitations.md`.

The production extractor is deliberately rule-based. An opt-in pretrained token-classification adapter is available for evaluation only; it is not enabled in normal processing and does not replace rules when it fails. The prototype does not fabricate model confidence, diagnosis, results, or clinical summaries. Scanned-image OCR is attempted only when Tesseract and its Python wrapper are installed; otherwise a warning is saved and shown. PDF text extraction uses PyMuPDF. Image OCR uses pytesseract. Uploaded content stays local; there is no configured external LLM call.

## Run locally

1. Install Python 3.11+ and Node.js 22.12+.
2. From the repository root, create the project-local environment and install the pinned backend set:

   ```powershell
   py -3.11 -m venv backend\.venv
   .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
   ```

3. Copy `.env.example` to `.env` at the repository root. Replace the placeholder `MEDNLP_SECRET_KEY` with a long random value. Keep `.env` private.
4. Start the API from `backend`:

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   Startup applies the Alembic schema and recovers locally queued/interrupted report jobs. Health is at `/api/v1/health`; OpenAPI is at `/docs`.
5. In another terminal, install the exact frontend lockfile and start Vite:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

   The Vite proxy forwards `/api` to `http://127.0.0.1:8000`.

PyMuPDF is installed with the Python requirements. `pytesseract` is included, but scanned-page OCR also requires the native Tesseract executable installed separately. Add `tesseract.exe` to `PATH` or set `MEDNLP_TESSERACT_CMD` to its full Windows path; restart the backend and check `/api/v1/health` for its availability/path. Without it, OCR is unavailable and extraction warnings are shown. The backend accepts PDF, PNG, and JPEG up to the configured 20 MB default (set `MEDNLP_MAX_UPLOAD_BYTES` to change it), up to the configured page limit. Storage is outside the frontend public directory.

## Verification

Validate the synthetic annotations and run the v3 frozen before/after comparison from `backend`:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.evaluation.validate_annotations
.\.venv\Scripts\python.exe -m app.evaluation.run_quality_v3
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp
```

The v3 runner writes `data/synthetic/evaluation.v3.{json,csv,md}` and preserves the earlier v1/v2 files. On the same seven-document/24-annotation synthetic held-out set, strict-span F1 changed from 0.723 before parser changes to 0.936 after. This small project-authored synthetic result is not clinical evidence or a real-world performance estimate; the v3 pretrained baseline is `not_run`, with no score. See `docs/evaluation.md` for protocol, denominators, and limitations.

The optional biomedical NER adapter uses `d4data/biomedical-ner-all` at revision `e2272cd5d96cb445524015fc5d9c1e198224a3bc` with an explicit subset label map. Core setup does not install Transformers, PyTorch, or model weights. To opt in, install `backend/requirements-model.txt` (or the tested closure in `backend/requirements-model-lock.txt`), set `MEDNLP_RUN_MODEL=1` and optionally `MEDNLP_NER_MODEL`/`MEDNLP_NER_REVISION`, then run the evaluation module. It remains an evaluation-only adapter and is not enabled in normal processing. Historical v2 model results are documented separately; no pretrained model was run for v3. See `docs/evaluation.md` for prior model timing, labels, truncation behavior, license scope, and limitations. Tesseract is unavailable on this machine.

The frontend production build is checked with `npm run build` from `frontend`. Three source-linked summary-review examples are pending at `data/synthetic/summary_reviews.v2.jsonl`; they contain no human scores. Current results are documented in `docs/evaluation.md`, the product audit in `docs/implementation_audit.md`, and remaining risks in `docs/limitations.md`. Browser flows have not been verified; see `docs/manual_browser_verification.md` for repeatable local checks.
See `docs/architecture.md`, `docs/privacy.md`, `docs/annotation_guidelines.md`, and `docs/limitations.md` before adapting this prototype.

## Synthetic demonstration reports

`data/synthetic/demo_reports/` contains eight fictional PDF fixtures across laboratory, discharge, and radiology report types. Six shorter reports cover diabetes, chronic kidney disease, pneumonia, an indeterminate lung opacity, iron studies, and heart-failure medication reconciliation. The other two are longer cases: a four-page admission-to-discharge patient record and a three-page multi-disease differential assessment. Their intended behavior coverage is indexed in `data/synthetic/demo_reports/README.md` and `manifest.json`. Every fixture is synthetic, visibly labeled, and intended for demonstrations and regression tests only; it is not clinical guidance. Regenerate them with `python -m app.evaluation.create_demo_reports` from `backend`.
