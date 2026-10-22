# Synthetic evaluation v3

Project-team-authored synthetic regression results only. No independent annotation, adjudication, clinical validation, or real-world performance estimate is available.

- Dataset: `data/synthetic/annotations.v2.jsonl`
- Development documents: 13
- Held-out synthetic evaluation documents: 7
- Exact span convention: exact source-text offsets; Unicode text is not normalized; zero-based, end-exclusive Python string indices, page-relative
- Duplicate guard: {'method': 'case-folded, whitespace-collapsed SequenceMatcher ratio', 'threshold': 0.92, 'scope': 'all document pairs, including within a split'}

## Baseline comparison

| Baseline | Status | Documents | Gold annotations | Predictions | TP | FP | FN | Precision | Recall | Strict-span F1 | Source-span integrity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Rules (unchanged) | available | 7 | 24 | 23 | 17 | 6 | 7 | 0.739 | 0.708 | 0.723 | 23/23 (1.000) |
| Rules (improved) | available | 7 | 24 | 23 | 22 | 1 | 2 | 0.957 | 0.917 | 0.936 | 23/23 (1.000) |
| d4data/biomedical-ner-all | not_run | — | — | — | — | — | — | — | — | — | — |

d4data/biomedical-ner-all result: Optional pretrained inference was not requested; no pretrained score is reported.

## Entity results by type

| Entity type | TP | FP | FN | Precision | Recall | Strict-span F1 |
|---|---:|---:|---:|---:|---:|---:|
| diagnosis_or_symptom | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| differential_evidence_against | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| differential_evidence_for | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| differential_possibility | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| differential_status | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| laboratory_result | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| medication | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| radiology_finding | 3 | 0 | 2 | 1.000 | 0.600 | 0.750 |
| radiology_impression | 0 | 1 | 0 | 0.000 | 0.000 | 0.000 |

## Entity results by report type

| Report type | TP | FP | FN | Precision | Recall | Strict-span F1 |
|---|---:|---:|---:|---:|---:|---:|
| discharge | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| laboratory | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| radiology | 3 | 1 | 2 | 0.750 | 0.600 | 0.667 |

## Context and extraction attributes

| Attribute | Correct | Eligible exact-span matches | Unavailable attribute | Accuracy |
|---|---:|---:|---:|---:|
| negation | 22 | 22 | 0 | 1.0 |
| uncertainty | 22 | 22 | 0 | 1.0 |
| temporality | 18 | 22 | 0 | 0.8181818181818182 |
| assertion_status | 3 | 3 | 0 | 1.0 |

## Medications

| Field | Correct | Matched medication spans with both values | Gold values present | Exact-match accuracy |
|---|---:|---:|---:|---:|
| medication_name | 0 | 0 | 0 | — |
| dose | 0 | 0 | 0 | — |
| route | 0 | 0 | 0 | — |
| frequency | 0 | 0 | 0 | — |
| duration | 0 | 0 | 0 | — |
| medication_change | 0 | 0 | 0 | — |

## Document classification

- Accuracy: 7/7 (1.000)

| Report type | Precision | Recall | F1 |
|---|---:|---:|---:|
| laboratory | 1.000 | 1.000 | 1.000 |
| discharge | 1.000 | 1.000 | 1.000 |
| radiology | 1.000 | 1.000 | 1.000 |
| unknown | 1.000 | 1.000 | 1.000 |

## Errors and limits

- Rule processing failures: 0
- Unsupported/unknown-type documents: 1
- Unmatched predictions (strict-span false positives): 1
- An unmatched prediction is an exact-span metric error, not a human adjudication that the source claim is unsupported.
- Model status: not_run
- Model reason: Optional pretrained inference was not requested; no pretrained score is reported.
- Attribute metrics apply only to strict-span matches where both annotation and predictor supplied the attribute.
- Source-span integrity confirms offsets resolve to original source text. It does not establish semantic correctness or that a linked passage supports a claim.
- Results are preliminary because the corpus is small, synthetic, and not independently reviewed.

## Differential evidence links

- Exact linked evidence count: 6 correct / 6 annotated; predicted 6; precision 1.0, recall 1.0, F1 1.0.
- Interpretation: Exact evidence-item and differential-possibility span endpoints plus relation label; preliminary synthetic labels.
