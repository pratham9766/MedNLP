# MedNLP Insight

MedNLP Insight is an informational research prototype for evidence-linked analysis of synthetic or user-provided medical reports. It is not a diagnostic system or a substitute for professional medical judgment. Do not use it for emergency or treatment decisions.

## Current status

This repository was empty at intake. The implementation provides a FastAPI service, local SQLite persistence, PBKDF2 password hashing and signed bearer-token authentication, per-user document ownership, private file storage, PDF/image text extraction, deterministic report classification and extraction, evidence citations, report-scoped extractive question answering, review annotations, JSON export, and a React/TypeScript UI. Processing currently runs in a local background thread; this is suitable only for development. Production PostgreSQL migrations, persistent job workers, and model-based inference remain deployment work and are described in `docs/limitations.md`.

The extractor is deliberately rule-based. It does not fabricate model confidence, diagnosis, results, or summaries. Scanned-image OCR is attempted only when Tesseract and its Python wrapper are installed; otherwise a warning is saved and shown. PDF text extraction uses PyMuPDF. Image OCR uses pytesseract. Uploaded content stays local; there is no configured external LLM call.

## Run locally

1. Install Python 3.11+ and Node.js 20+.
2. In `backend`, create an environment and run `pip install -r requirements.txt`.
3. Copy `.env.example` to the repository root `.env` and set a private `MEDNLP_STORAGE_DIR` and a long random `MEDNLP_SECRET_KEY`.
4. Start the API from `backend` with `uvicorn app.main:app --reload`. The API initializes its SQLite database on startup and serves OpenAPI at `/docs`.
5. In `frontend`, run `npm install` and `npm run dev`. The Vite proxy forwards `/api` to `http://127.0.0.1:8000`.

PyMuPDF is installed with the Python requirements. For image OCR, install the Tesseract executable for your operating system and `pytesseract`; check `/api/v1/health` for component availability. The backend accepts PDF, PNG, and JPEG up to the configured size limit. Storage is outside the frontend public directory.

## Verification

From `backend`, run `pytest`. From `frontend`, run `npm run build`. Synthetic fixtures and evaluation instructions are in `data/synthetic` and `docs/evaluation.md`. The included evaluation runner reports classification accuracy/macro-F1 and extraction exact match on the tiny illustrative fixture set; it is not a clinical benchmark and does not establish accuracy or generalization.

See `docs/architecture.md`, `docs/privacy.md`, `docs/annotation_guidelines.md`, and `docs/limitations.md` before adapting this prototype.
