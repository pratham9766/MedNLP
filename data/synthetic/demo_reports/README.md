# Synthetic demonstration report pack

This folder contains eight fictional PDF reports, their extracted-text companions, and `manifest.json`. Six short reports cover laboratory, discharge, and radiology workflows. Two longer cases provide the requested dense patient record and multi-disease differential workup: a four-page admission-to-discharge summary and a three-page assessment that keeps evidence for and against several possibilities visible. The cases exercise different conditions and supported report types while preserving uncertainty and source context. They are not real patient records, clinical guidance, or an evaluated clinical dataset.

| PDF | Main scenario | Expected type | Suggested review focus |
|---|---|---|---|
| `01_type2_diabetes_metabolic_followup.pdf` | Type 2 diabetes follow-up laboratory panels | Laboratory | Multi-analyte results, flags, report ranges, urine albumin ratio |
| `02_chronic_kidney_disease_chemistry.pdf` | CKD referral with serial renal chemistry | Laboratory | Units, prior values, missing reference intervals, no inferred stage |
| `03_community_acquired_pneumonia_discharge.pdf` | Respiratory infection discharge summary | Discharge | Documented diagnosis, differential, medication course, follow-up request |
| `04_chest_ct_indeterminate_opacity.pdf` | Chest CT with indeterminate opacity | Radiology | Findings vs. impression, uncertainty, negative findings, recommendation |
| `05_microcytic_anemia_iron_studies.pdf` | CBC and iron studies | Laboratory | Multi-panel parsing, flags, source-based results, cause not supplied |
| `06_heart_failure_discharge_medication_reconciliation.pdf` | Heart-failure discharge and medication reconciliation | Discharge | Dose/route/frequency, held vs. continued items, historical context |
| `07_comprehensive_patient_admission_discharge.pdf` | Detailed fictional patient encounter from history through discharge | Discharge | Dense narrative, medications, symptoms vs. diagnoses, labs, follow-up, evidence review |
| `08_complex_differential_diagnosis_workup.pdf` | Multidisease differential assessment for exertional breathlessness | Discharge | Five attributed possibilities, evidence for/against, negation, uncertainty, incomplete workup |

## Use for product demonstrations

1. Start the local API and frontend using the commands in the repository README.
2. Sign in to a local synthetic test account and upload one PDF at a time.
3. Check that status reaches `completed` or `completed_with_warnings`, then open the report.
4. Follow entity and summary evidence links back to page text. Confirm the quoted text is visible on the source page.
5. Review medication detail, lab values and flags, radiology uncertainty, and follow-up recommendations against the source.
6. Try one answerable question and one unsupported question. Verify quotations for the former and abstention for the latter.
7. Make a test correction, reload, and confirm the source extraction remains available; export JSON and inspect the correction and review history.
8. For the long cases, check that the result list remains scannable and that source excerpts take you to the correct page. Ask which differential diagnosis was confirmed: the report intentionally does not establish one, so the answer must not invent it.

The app uses deterministic rules. A missed or broad extraction is a useful review/test case; do not present the generated output as a diagnosis. The PDFs visibly identify themselves as synthetic, and the manifest records their intended report type and review focus.

Regenerate the fixtures from the repository root with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.evaluation.create_demo_reports
```

Run the fixture tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_demo_reports.py
```
