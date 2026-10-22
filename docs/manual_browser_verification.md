# Manual browser verification checklist

Automated browser verification was unavailable for the v3 milestone. Use this checklist after restoring the local Python environment and starting the app using the commands in the root `README.md`. Use only synthetic demonstration documents and test accounts.

## Setup

1. From the repository root, follow `README.md` to create `backend/.venv`, install `backend/requirements-lock.txt`, set a private local `MEDNLP_SECRET_KEY`, and start the API.
2. In a second terminal, run `npm ci` and `npm run dev` from `frontend`.
3. Open the local Vite URL, register a disposable test account, and sign in.
4. Use the fictional report pack in `data/synthetic/demo_reports/`. Do not upload real patient data for this check.

## Report workflow

1. Upload `03_community_acquired_pneumonia_discharge.pdf`; wait for processing to finish and open the report.
2. Leave one review-required item pending. Confirm the report status still indicates review is needed and that the UI does not imply completion.
3. Mark the remaining required items reviewed/corrected. Confirm the report status changes only when every required item is resolved. Reopen one reviewed item and confirm the report returns to the review queue.
4. Select a source-evidence link from an extracted item and confirm the expected source page and quoted text are shown. Open the original PDF and confirm it remains available when exact text highlighting is unavailable.
5. Upload `08_complex_differential_diagnosis_workup.pdf`. Confirm each differential possibility remains a separate possibility, its report wording/status is visible, and only explicitly linked support/limiting passages appear under it. Confirm uncertainty is not presented as a confirmed diagnosis.
6. Upload `04_chest_ct_indeterminate_opacity.pdf`. Check that negative, uncertain, historical, and current statements remain distinguishable and source-linked.
7. Export the report JSON and confirm its source references and review state agree with the UI.

## Failure and access checks

1. Upload a small scanned/image-only report while native Tesseract is unavailable. Confirm the report shows the OCR/unavailable warning and does not present empty extraction as a successful clean analysis. Check `/api/v1/health` for the OCR availability state.
2. Register a second disposable account in a private browser session. Attempt to open the first account's report using its report URL and any file/evidence URL copied from that report. Confirm access is denied and the second account cannot see or export the first account's report.
3. Record browser, OS, app commit, test date, report IDs, screenshots, and pass/fail notes. Do not mark annotation or summary-review records as independently reviewed based on this UI smoke test; it does not adjudicate summary correctness.
