# Limitations and deployment gaps

MedNLP Insight is a research prototype and must not be used to make diagnosis or treatment decisions.

Report review policy: items require review by default. A clean `completed` report is `reviewed` only after every review-required item is marked reviewed/corrected; a clean completed report with zero review-required items is considered complete. Any warning-bearing extraction remains `needs_review`, even if its visible items were reviewed, because the warning may indicate missing source coverage. Failed or in-progress processing cannot be marked reviewed. Reopening any item returns its report to the review queue. This is workflow bookkeeping, not clinical sign-off.

The export payload was additively versioned to 1.1 for structured overview/differential fields and reopened-review history. Existing stored analysis payloads at version 1.0 are still accepted; new output uses version 1.1.

- Alembic migrations now define the initial schema. A complete pre-migration schema is baseline-stamped on first startup to preserve existing rows; a partial legacy schema stops startup for manual review. A production database deployment and migration coverage beyond the initial baseline remain outstanding.
- Processing status is persisted and queued/interrupted work is rescheduled at startup. Execution still uses an in-process thread pool; there is no cross-process job claim, worker isolation, cancellation, or durable attempt history. Run one API worker only until a shared queue/locking design is added.
- The production path uses deterministic rules. The pinned Transformers baseline is evaluation-only; it is not calibrated, connected to production analysis, or clinically validated.
- Lab range comparison is limited to unambiguous numeric values, matching explicit units, and parseable report intervals. Reported flags are preserved as reported and are not clinical judgments.
- Discharge, medication, and radiology parsing is heuristic. Negation, uncertainty, temporality, modality, and section labels are review cues, not validated clinical relationships.
- OCR requires the native Tesseract executable. It was unavailable during this implementation audit. Handwriting recognition is not supported.
- Authentication remains prototype-grade. Login failures are throttled in process memory only; token revocation, robust multi-process rate limiting, CSRF/XSS defenses, production secrets management, CSP review, and operational monitoring remain outstanding.
- Audit history is available in JSON export, but there is no audit administration interface. Retention configuration is not enforced by a deletion scheduler.
- No formal dependency vulnerability scan or production deployment scan has been completed. The backend suite now contains 65 tests; the v3 milestone run passed them using Python 3.11 with the project’s existing virtual-environment packages on `PYTHONPATH`. The checked-in project venv launcher currently points at a missing base Python installation. Browser verification remains outstanding because browser automation could not initialize in the current environment.
- Evaluation uses 20 project-team-authored synthetic documents (13 development, 7 held out). No independent annotation or review was performed; all annotation records remain marked pending/unreviewed. No human summary adjudication, QA support evaluation, OCR CER/WER, confidence intervals, real-data reliability study, or clinical evaluation is available. The v3 extraction change improved exact-span F1 from 0.723 to 0.936 on these seven synthetic reports only; this is not a general performance estimate.
- The original PDF/image can now be opened through the ownership-checked file endpoint. Evidence navigation links to extracted text and its page; exact PDF text highlighting is unavailable because rendered-page coordinates are not stored. Browser verification remains outstanding.
- There is no FHIR interface, multi-tenant organization management, comprehensive settings area, or audit administration UI.

See `docs/evaluation.md` for measured results and denominators and `docs/privacy.md` for data handling.

## Production readiness checklist

This prototype is **not production ready, clinically validated, or security certified**. Before any deployment with real patient records, complete and independently verify at least:

- Human-reviewed, patient-separated evaluation data and adjudicated summary, extraction, differential, and evidence-link metrics.
- Backend API, authentication/session, authorization, XSS, dependency, and deployment security reviews; revocable sessions and a shared rate limiter.
- A persistent multi-worker job queue or database claim/lease mechanism, restart and concurrency tests, and operational monitoring/backup restore drills.
- Migration tests against a copy of each supported existing database, plus an explicit backup-and-rollback procedure.
- OCR installation checks and scanned-document error/quality tests for each supported deployment host.
- Enforced retention/deletion policy, storage encryption/access controls appropriate to the host, and privacy/legal review for the intended setting.
- Browser verification of upload, review/reopen, source viewer, export, responsive layout, and cross-user denial workflows.
