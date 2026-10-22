# Implementation audit

Audit date: 2026-10-21. Scope: the requested end-to-end product implementation, evidence reliability, usability, and production-readiness review. This is a local prototype audit; no browser-level verification or production deployment was performed.

## Feature inventory

| Area | State | Evidence / gap |
|---|---|---|
| Authentication and per-user document ownership | Implemented, but inadequately tested this turn | Workflow assertions exist in `test_api_workflow.py`; the Windows asyncio socketpair stall prevented API execution. No security penetration review. |
| Upload validation and private storage | Implemented and unit-tested in part | Signature, parser, size, page and image-bound checks have focused coverage; complete HTTP upload workflow was blocked. |
| PDF text extraction and OCR fallback | Partially implemented | Native text extraction and visible OCR warnings are implemented. Tesseract is absent, so actual OCR output quality was not verified. Handwriting is unsupported. |
| Type classification | Implemented and evaluated synthetically | Unknown/tied classification abstains; synthetic classification was 6/6. User correction/reclassification of document type is missing. |
| Lab/discharge/radiology extraction | Partially implemented | Type-specific deterministic fields and contextual flags exist, but parsers remain heuristic and synthetic evaluation is small. |
| Evidence spans and summary citations | Implemented and unit-tested | Pydantic validates source-page offsets; summary review record offsets validate. No rendered-PDF coordinates are claimed. |
| Grounded Q&A | Implemented, not verified in this run | Existing lexical retrieval/abstention returns report quotations. API workflow checks could not run; broader answer-support evaluation is missing. |
| Human corrections and audit export | Implemented, but inadequately tested this turn | Code preserves originals and emits actor-linked history; tests exist in blocked API suite. No UI to browse audit history. |
| Durable jobs, migrations, production hosting | Missing | Work remains in-process with SQLite `create_all`; no persistent queue, Alembic migrations, or production deployment. |
| Browser workflow and responsive behavior | Blocked/unverified | Computer-use helper stopped because it could not determine the current Edge URL. Manual checklist is required. |
| OCR runtime / real clinical evidence | Blocked by infrastructure/governance | Tesseract is unavailable; no approved real-data set or independent review is present. |

## Delivered in this pass

- **Upload safety and limits:** validates supported PDF/PNG/JPEG content, signatures/readability, zero-byte files, configured byte/page limits, image format, and pixel bounds before saving.
- **Extraction reliability:** bounded OCR fallback for sparse PDF text and images; missing or failed OCR is exposed as a warning and completion-with-warnings state.
- **Evidence integrity:** validates entity and summary spans against source page text. Summary statements carry clickable source references. Export has a typed response contract and JSON Schema.
- **Clinical data restraint:** lab numeric/comparator/qualitative fields are extracted where unambiguous; range checks require compatible stated units and ranges. Classification abstains as unknown on ambiguous positive ties. Discharge/radiology fields preserve section/context cues and uncertainty markers.
- **Review and audit:** corrections preserve extracted originals, duplicate correction submissions are idempotent, and audit rows record the authenticated actor. Export includes review history. Deletion checks the storage root and attempts rollback-safe file cleanup.
- **Frontend usability:** upload limits are read from health configuration; report filtering/status handles warning completions; evidence links navigate the text source; parsed fields and corrections are visible.
- **Configuration:** configurable CORS, upload bytes and maximum pages; startup enforces a non-default signing secret of adequate length.
- **Reproducible artifacts:** evaluation writes `evaluation.v2.*`; prior `evaluation.v1.*` artifacts were retained. Summary review generation writes `summary_reviews.v2.jsonl` and leaves the prior set untouched.

## Verification

- `backend`: `tests/test_nlp.py` and `tests/test_evaluation.py` — **23 passed**.
- `frontend`: `npm run build` — **passed**.
- Synthetic source annotations: **14 validated**, including exact source spans and patient-group/split checks.
- Summary review set: **3 pending cases validated**; no human review scores were assigned.
- Full API workflow suite: attempted, but the environment stalled while initializing Windows asyncio loopback sockets before the first request. This is an environment blocker, not a passing result.
- Browser flows and deployed production behavior: **not verified**.

See `docs/evaluation.md` for rule/model scores and their limits. `docs/limitations.md` lists the remaining production work.

## Follow-up implementation pass — 2026-10-22

- Fixed report review status to derive from all required item states and processing completeness; added a reopen action, zero-item policy, startup repair for stale report status, and API regression cases.
- Added source-linked patient overview sections and report-attributed differential possibilities, including explicit support/limiting passage references. New exports use schema 1.1; legacy 1.0 analysis payloads remain accepted.
- Added local original-PDF/image viewing via the authenticated ownership-checked file endpoint. Page navigation and PDF zoom/fit-to-width are available. Precise text highlights remain unsupported because PDF coordinates are not extracted.
- Added an initial Alembic schema, safe baseline stamping for complete existing schemas, persisted queued-job recovery, process-local duplicate scheduling prevention, login throttling, response security headers, database readiness, and configurable Tesseract path detection.
- Corrected the README's eight-report count and added a count-drift assertion.
- **Verified:** nine frontend tests passed; TypeScript and production build passed; Python 3.12 syntax compilation and direct Pydantic/extractor checks passed on all eight synthetic text companions, including five cited possibilities in the differential case.
- **Not verified:** backend/API and Alembic integration suites, PDF rendering/browser workflows, OCR execution, multi-process job safety, and changed held-out metrics. The checked-in held-out evaluation numbers remain unchanged; differential smoke checks do not establish accuracy.

## Manual browser checklist

Browser automation did not reach the local app. After starting the API and Vite as described in `README.md`, manually verify with synthetic fixtures only:

1. Register and sign in with a synthetic test account.
2. Upload the synthetic lab, discharge, and radiology examples; confirm queued/processing and terminal statuses.
3. Open each analysis, follow summary and entity evidence to the correct page text, and check warning presentation.
4. Ask one answerable and one unsupported question; check source quotes and abstention.
5. Correct an entity, reload, and verify the correction persists while extracted source text remains intact.
6. Export JSON; validate it against `docs/schemas/export.v1.1.schema.json` and check correction/reviewer history.
7. Check report type/status filters, keyboard navigation, empty/error states, and narrow viewport layout.
8. Verify a second account cannot read the first account's report; delete the synthetic report and confirm it disappears.
