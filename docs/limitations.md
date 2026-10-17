# Limitations and deployment gaps

- Username/password auth and per-user checks are implemented for the prototype, but production hardening remains: token rotation/revocation, login throttling, CSRF/XSS threat review, and secret enforcement. Do not expose the service without deployment review.
- SQLite `create_all` is used for development. Alembic migrations, PostgreSQL JSONB, and production database setup are outstanding.
- Background jobs run in memory and are lost on process restart; retry and queue persistence are outstanding.
- Extraction uses rules only. No spaCy/scispaCy or pretrained biomedical model baseline is integrated. No clinical claims, calibrated confidence, or accuracy claim is made.
- Discharge and radiology extract candidate source lines, not fully normalized clinical relationships. Review and negation/historical interpretation are incomplete.
- Lab abnormal flags are intentionally not inferred yet. Ranges and units are preserved as text.
- OCR requires a separately installed Tesseract executable; no bundled OCR runtime exists.
- UI upload is basic and does not yet provide document preview, byte-level progress events, filters by report type/date, rename, or comprehensive settings/deletion preferences.
- Evaluation fixtures are synthetic and tiny. The framework does not yet measure QA quality, grounded-summary support, OCR CER/WER, patient-level splits, or reliability across held-out annotated real data.
- Rate limiting, CSRF/session defenses, audit review/export, Alembic migration tests, adversarial OCR evaluation, and retention enforcement remain outstanding.

This is an informational research prototype, not a diagnostic system or a substitute for professional medical judgment.
