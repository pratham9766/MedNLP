# Limitations and deployment gaps

- Username/password auth and per-user checks are implemented for the prototype, but production hardening remains: token rotation/revocation, login throttling, CSRF/XSS threat review, and secret enforcement. Do not expose the service without deployment review.
- SQLite `create_all` is used for development. Alembic migrations, PostgreSQL JSONB, and production database setup are outstanding.
- Background jobs run in memory and are lost on process restart; retry and queue persistence are outstanding.
- Production extraction uses rules only. An opt-in Transformers adapter for `d4data/biomedical-ner-all` is implemented for evaluation, but is not connected to production processing and has not been run because optional dependencies and weights are absent. No clinical claims, calibrated confidence, or clinical accuracy claim is made.
- Discharge and radiology extract candidate source lines, not fully normalized clinical relationships. Negation, uncertainty, and historical tags are heuristic review cues, not validated interpretation.
- Lab range status is assigned only when a plain numeric value, explicit unit, and parseable low-high range appear together; otherwise no flag is assigned. This is a deterministic comparison to the report's own interval, not a clinical interpretation.
- OCR requires a separately installed Tesseract executable; no bundled OCR runtime exists.
- UI upload is basic and does not yet provide document preview (page text is the fallback), byte-level progress events, date filters, rename, or comprehensive settings/deletion preferences. The UI review editor records a corrected value while preserving the extracted original; reviewer identity/history browsing is not yet presented in the UI.
- Evaluation annotations and outputs are synthetic and tiny. They include patient-group split checks, strict spans, selected lab attributes, and negation/uncertainty measures. The optional model comparison and manually adjudicated summary scores have not run. QA correctness/support, OCR CER/WER, confidence intervals, and real-data reliability remain unmeasured.
- Rate limiting, CSRF/session defenses, audit review/export, Alembic migration tests, adversarial OCR evaluation, and retention enforcement remain outstanding.

This is an informational research prototype, not a diagnostic system or a substitute for professional medical judgment.
