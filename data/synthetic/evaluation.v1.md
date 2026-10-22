# Synthetic evaluation v1

This is a small, manually labeled synthetic set. It is not clinical evidence and does not estimate performance on real reports. Development and evaluation partitions use disjoint synthetic patient groups and cross-split near-duplicate checks. Examples were authored within the project team, not independently adjudicated.

- Development documents: 8
- Synthetic evaluation documents: 6
- Labeled entities in evaluation split: 12
- Rule document-type accuracy: 6/6 (1.000)

## Strict-span comparison

| Baseline | Status | TP | FP | FN | Precision | Recall | Strict-span F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Rules | available | 9 | 3 | 3 | 0.750 | 0.750 | 0.750 |
| d4data/biomedical-ner-all | available | 0 | 17 | 12 | 0.000 | 0.000 | 0.000 |

## Rules: attributes and per-type metrics

- Lab value exact-match accuracy: 3/3 (1.000)
- Unit accuracy: 3/3 (1.000)
- Reference interval accuracy: 3/3 (1.000)
- Negation error rate: 0/9 (0.000)
- Uncertainty error rate: 0/9 (0.000)

| Entity | TP | FP | FN | P | R | Strict F1 |
|---|---:|---:|---:|---:|---:|---:|
| diagnosis_or_symptom | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| laboratory_result | 3 | 1 | 1 | 0.750 | 0.750 | 0.750 |
| medication | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| radiology_finding | 3 | 2 | 2 | 0.600 | 0.600 | 0.600 |

## Pretrained runtime and limitations

- Model revision: `e2272cd5d96cb445524015fc5d9c1e198224a3bc`
- Load time: 26.44910979999986 seconds; inference: 0.5486534999945434 seconds total, 0.09144224999909056 seconds/document
- Device: cpu; parameter count: 66427476; max positions: 512
- RSS after inference: unavailable (psutil not installed)
- Tokenizer: DistilBertTokenizerFast; fast tokenizer: True
- Processing failures: rules 0; model 0; unsupported evaluation docs: 1
- Model status detail:

Exact-span matching includes document ID, page, offsets, and entity type. Small denominator results are descriptive regression measurements only; no confidence interval, independent benchmark claim, or clinical performance claim is made.
