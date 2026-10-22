# Synthetic evaluation v2
This is a small project-team-authored synthetic set. It is not clinical evidence and does not estimate performance on real reports. The partitions use disjoint synthetic patient groups and cross-split near-duplicate checks; independent adjudication was not performed.
- Development documents: 8
- Synthetic evaluation documents: 6
- Gold entities: 12
## Classification
- Accuracy: 6/6 (1.000)
| Actual \ Predicted | Lab | Discharge | Radiology | Unknown |
|---|---:|---:|---:|---:|
| laboratory | 2 | 0 | 0 | 0 |
| discharge | 0 | 1 | 0 | 0 |
| radiology | 0 | 0 | 2 | 0 |
| unknown | 0 | 0 | 0 | 1 |
| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| laboratory | 1.000 | 1.000 | 1.000 |
| discharge | 1.000 | 1.000 | 1.000 |
| radiology | 1.000 | 1.000 | 1.000 |
| unknown | 1.000 | 1.000 | 1.000 |
## Strict-span comparison
| Baseline | Status | TP | FP | FN | Precision | Recall | Strict-span F1 | Evidence-span accuracy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Rules | available | 8 | 3 | 4 | 0.727 | 0.667 | 0.696 | 11/11 (1.0) |
| d4data/biomedical-ner-all | available | 0 | 17 | 12 | 0.000 | 0.000 | 0.000 | 17/17 (1.0) |
## Rules: attributes and per-entity metrics
- Lab normalized-value exact match: 3/3 (1.0)
- Unit exact match: 3/3 (1.0)
- Reference-interval exact match: 3/3 (1.0)
- Negation errors: 0/8 (0.0)
- Uncertainty errors: 0/8 (0.0)
| Entity | TP | FP | FN | Precision | Recall | Strict F1 |
|---|---:|---:|---:|---:|---:|---:|
| diagnosis_or_symptom | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| laboratory_result | 3 | 1 | 1 | 0.750 | 0.750 | 0.750 |
| medication | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| radiology_finding | 2 | 1 | 3 | 0.667 | 0.400 | 0.500 |
| radiology_impression | 0 | 1 | 0 | 0.000 | 0.000 | 0.000 |
## Model and limits
- Revision: `e2272cd5d96cb445524015fc5d9c1e198224a3bc`
- Load: 67.639477299992 seconds; inference: 0.7014084000256844 seconds total, 0.11690140000428073 seconds/document
- Device: cpu; parameters: 66427476; maximum positions: 512
- RSS: unavailable (psutil not installed)
- Processing failures: rules 0; model 0
- Model status detail:
Exact span requires matching document, page, offsets, and entity type. Attribute and contextual measures use their stated match denominators. These descriptive regression measurements are not clinical-performance claims.