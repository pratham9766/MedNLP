# Synthetic evaluation v1

This is a small, manually labeled, authored synthetic set. It is not clinical evidence and does not estimate performance on real reports. The evaluation split is separate by synthetic patient group and checked for near duplicates; authorship is shared, so it is not an independent research benchmark.

- Development documents: 5
- Synthetic evaluation documents: 6
- Labeled entities: 12
- Rule document-type accuracy: 6/6 (1.000)
- Strict entity spans: TP 9, FP 3, FN 3
- Precision 0.750; recall 0.750; strict-span F1 0.750
- Lab value exact-match accuracy: 3/3 (1.000)
- Unit accuracy: 3/3 (1.000)
- Reference interval accuracy: 3/3 (1.000)
- Negation error rate: 0/9 (0.000)
- Uncertainty error rate: 0/9 (0.000)
- Processing failures: 0; unsupported docs: 1
- Pretrained baseline: unavailable — ModuleNotFoundError: No module named 'transformers'

Small denominator results are descriptive regression measurements only. No confidence or clinical performance claim is made.
