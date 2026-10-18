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

   Startup initializes the configured SQLite database. Health is at `/api/v1/health`; OpenAPI is at `/docs`.
5. In another terminal, install the exact frontend lockfile and start Vite:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

   The Vite proxy forwards `/api` to `http://127.0.0.1:8000`.

PyMuPDF is installed with the Python requirements. `pytesseract` is included, but scanned-page OCR also requires the native Tesseract executable installed separately and available on `PATH`; restart the backend and check `/api/v1/health` after installing it. Without it, OCR reports unavailable and the analysis includes an extraction warning. The backend accepts PDF, PNG, and JPEG up to 20 MB. Storage is outside the frontend public directory.

## Verification

Validate and regenerate the versioned synthetic evaluation outputs from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.validate_annotations
.\.venv\Scripts\python.exe -m app.evaluation.run
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp
```

The evaluation runner writes `data/synthetic/evaluation.v1.{json,csv,md}`. Its synthetic evaluation partition has six documents and 12 manually labeled entities, with patient-separated development and evaluation groups plus cross-split near-duplicate checks. The rule baseline currently measures strict-span precision 0.750, recall 0.750, and F1 0.750 on this tiny authored synthetic set. These are descriptive regression measurements, not clinical evidence or real-world performance estimates. The former three-example smoke scores are a historical artifact only. See `docs/evaluation.md` for denominators and limitations.

The optional biomedical NER adapter uses `d4data/biomedical-ner-all` with an explicit subset label map. Core setup does not install Transformers, PyTorch, or model weights. To opt in, install `backend/requirements-model.txt`, set `MEDNLP_RUN_MODEL=1` and optionally `MEDNLP_NER_MODEL`/`MEDNLP_NER_REVISION`, then run the evaluation module. Use an immutable model revision for research runs. The optional load was attempted and returned `ModuleNotFoundError: No module named 'transformers'`; no model weights were downloaded. Tesseract is also unavailable on this machine.

The frontend production build is checked with `npm run build` from `frontend`. Historical Phase 2 validation covered 13 backend tests and a browser smoke workflow on the synthetic lab PDF. Phase 3 adds annotation schema/offset, metric, adapter mapping/failure, QA evidence, summary review metric, and correction/export assertions. Current outcomes are reported after the Phase 3 verification run.
See `docs/architecture.md`, `docs/privacy.md`, `docs/annotation_guidelines.md`, and `docs/limitations.md` before adapting this prototype.
