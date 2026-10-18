# Evaluation protocol and current results

## What the former smoke runner measured

`data/synthetic/fixtures.json` contains three short illustrative examples. Its former runner computed document-type accuracy and macro-F1 over those three examples and a normalized string overlap score for lab rows on labeled fixtures. That score was not strict span F1, value accuracy, unit accuracy, or an independent held-out estimate. The same tiny examples were used during development; its perfect values were not evidence of generalization. The old output is retained only as a historical artifact and must not be cited as a benchmark.

## Annotation data

`data/synthetic/annotations.v1.jsonl` is a versioned JSONL dataset authored for software regression testing. Every document is explicitly synthetic; no real clinical evidence or patient data is included. The schema records document ID/type, synthetic patient group, split, page text, exact page-relative character offsets, original text, entity type, normalized value, unit, reference interval, negation, uncertainty, temporality, relations, and provenance. Empty entity lists mark unsupported/empty content. Challenging cases include OCR-like `1.O`, missing units/ranges, a malformed OCR-like unit (`mmoI/L`), two lab results on one row, negation, uncertainty, historical mentions, contradictory statements, and unknown/empty documents.

Guidelines: retain source spelling exactly; offsets are zero-based and end-exclusive within the corresponding page text; never infer absent values, units, intervals, temporality, or relations; annotate context cues only when the text supports them; unknown/empty docs have no fabricated labels. Synthetic IDs and patient groups are arbitrary and do not refer to people.

The `development` and `synthetic_eval` partitions have disjoint synthetic patient-group identifiers. The runner also rejects patient overlap and cross-split near-duplicate text (normalized similarity at least 0.92). These examples were authored by the same project team and are not an independent dataset. Their small descriptive results must not be represented as research benchmark or clinical performance.

## Reproduce

From `backend` with the project virtual environment active:

```powershell
python -m app.evaluation.validate_annotations
python -m app.evaluation.run
```

The validator checks schema, source offsets, patient grouping, and cross-split duplicate leakage. The runner writes `data/synthetic/evaluation.v1.json`, `.csv`, and `.md`. It evaluates rules on the same six synthetic evaluation documents as a configured optional model. Exact spans require identical page, start/end offsets, and entity type. Lab normalized value, unit, and interval are exact string comparisons (case- and whitespace-sensitive, with no numeric tolerance); they are compared only on correctly matched entity spans. Thus the attribute denominators are conditional on strict span matches, not all gold labs. Negation and uncertainty errors also use strict span matches; counts are emitted. Processing failures and unsupported document counts are explicit.

The checked-in current output was produced by executing the runner. Rule baseline: 6 synthetic evaluation documents, 12 annotated entities, strict-span precision 0.750, recall 0.750, F1 0.750. The sample is too small and synthetic to support performance claims. The optional model load was attempted but is **unavailable**: `transformers` is not installed in the core environment (`ModuleNotFoundError: No module named 'transformers'`). No model weights were downloaded. To opt in, install `backend/requirements-model.txt`, set `MEDNLP_RUN_MODEL=1`, optionally set `MEDNLP_NER_MODEL` and `MEDNLP_NER_REVISION`, then rerun. The model output records model ID and revision; use an immutable model revision for research use. Downloading weights is not part of normal tests.

## Model baseline scope

The optional adapter targets `d4data/biomedical-ner-all`, a DistilBERT token-classification model published under Apache-2.0. It accepts text and returns token spans. Only an explicit subset of labels is mapped (`Lab_value`, `Disease_disorder`, `Sign_symptom`, `Medication`, `Diagnostic_procedure`); all other labels are ignored. It does not supply reliable normalized values, units, ranges, negation, uncertainty, or temporality. Therefore the adapter must not be treated as a complete clinical extraction system. Load failures are recorded and return no predictions; rule predictions are not silently substituted.

References: [model card and license](https://huggingface.co/d4data/biomedical-ner-all), [published model label configuration](https://huggingface.co/d4data/biomedical-ner-all/blob/main/config.json), and [Transformers token-classification pipeline](https://huggingface.co/docs/transformers/main_classes/pipelines).

## Summary review and future evaluation

The current summary is a fixed description of extraction presence, not a clinical paraphrase. Q&A is extractive lexical retrieval over the selected report only, returns source passage page and character offsets, declines no-match questions, and does not execute text found inside a document. Contradictory polarity cues are surfaced for manual review. This is not a generative answer system.

`data/synthetic/summary_reviews.schema.json` defines the manually adjudicated format and `data/synthetic/summary_reviews.v1.jsonl` is a blank JSONL template with no fabricated review rows. Add one record per manually reviewed summary, with claim support, evidence correctness and spans, critical omissions, contradiction, review status, and reviewer ID. `summarize_review()` omits unreviewed records and reports denominators. No summary-review scores are currently available because no summary records have been adjudicated.

For authorized real-data evaluation, obtain governance/consent and licensing approval before use, independently annotate with a written protocol, split by patient, deduplicate before partitioning, freeze model revision and extraction configuration, and report sample sizes, exclusions, failure categories, and uncertainty intervals. Do not combine such results with the synthetic smoke measurements.
