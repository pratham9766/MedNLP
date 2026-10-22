# Evaluation protocol and results

## Current extraction-quality milestone (v3)

The current authored corpus is `data/synthetic/annotations.v2.jsonl`: 20 documents (13 development, 7 frozen `synthetic_eval`), 73 entity annotations, and no patient group crossing a split. All 20 documents are explicitly marked `not_independently_reviewed`. The expanded development cases add long multi-page discharge narratives, radiology time/context, OCR-like lab tables, medication changes, and explicit differential evidence. The added held-out case exercises differential candidates and linked support/limiting evidence. These examples were authored by the project team and are not independent labels.

`data/synthetic/evaluation.v3-baseline.*` records the original extractor before milestone tuning. `data/synthetic/evaluation.v3.*` compares that baseline and the improved extractor using the same frozen seven held-out reports and the corrected evaluator. Run from `backend`:

```powershell
$env:MEDNLP_ANNOTATIONS_PATH = "data/synthetic/annotations.v2.jsonl"
python -m app.evaluation.validate_annotations
python -m app.evaluation.run_quality_v3
python -m pytest -q --basetemp=.pytest-tmp
```

| Extractor | Held-out docs | Annotations | TP | FP | FN | Precision | Recall | Strict-span F1 | Source-span integrity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rules, before parser changes | 7 | 24 | 17 | 6 | 7 | 0.739 | 0.708 | 0.723 | 23/23 |
| Rules, after parser changes | 7 | 24 | 22 | 1 | 2 | 0.957 | 0.917 | 0.936 | 23/23 |

This is a +0.213 strict-span F1 change on a tiny, project-authored synthetic set, not an estimate of clinical or real-world performance. The improved result has one unmatched radiology-impression false positive and two missed radiology findings. Report-type classification was 7/7. Exact differential evidence-link scoring was 6/6 (F1 1.000); negation and uncertainty classification were each 22/22, temporality 18/22, and differential assertion status 3/3. Those attribute and relation denominators are small and use project-team-authored labels. Medication-field exact-match metrics are unavailable on held-out data because no held-out medication span has an independently scored populated medication field; development fixtures exercise parsing but do not substitute for held-out evidence. The optional pretrained baseline is `not_run` in v3 and has no v3 score.

The corrected exact-span scorer counts predictions as a multiset (duplicate extra detections are false positives), does not coerce missing context attributes to `false`, and includes unresolved or invalid source offsets in the source-span denominator as failures. Relation scores require exact evidence and possibility endpoints plus the relation label. Source-span integrity checks text/offset consistency, not whether a claim is semantically supported. Error examples and per-type/per-report-type breakdowns are in `data/synthetic/evaluation.v3.json` and `.md`.

Three source-linked generated-summary review records are available in `data/synthetic/summary_reviews.v2.jsonl`; all remain pending, with 0 human-reviewed summaries. See `docs/human_review_checklist.md` for the adjudication workflow. Human summary-support, omission, contradiction, and evidence-correctness rates remain unavailable until authorized reviewers complete and record those judgments.

## Annotation corpus

`data/synthetic/annotations.v1.jsonl` contains 14 authored synthetic documents: 8 development and 6 `synthetic_eval`, with 12 gold entities in the held-out split. It covers multi-analyte lab rows and several units, absent/malformed reference data, OCR-like `1.O`/`1O` and `mmoI/L`, radiology uncertainty/negation/conflicting statements, historical diagnoses, an unsupported note, and empty text. New examples were added only to development so the frozen six-document evaluation comparison remains unchanged. All examples were authored within the project team; there was no independent annotator or adjudication. The corpus is for software regression only, not a research benchmark or clinical evidence.

All spans are validated against exact page-relative source offsets. Patient groups cannot cross splits, and normalized cross-split near-duplicate text (similarity >= 0.92) is rejected. Empty entity lists represent unsupported/empty content, not missing annotation work. Run `python -m app.evaluation.validate_annotations` to verify the corpus.

## Reproduce baselines

From `backend` with the project environment active:

```powershell
python -m app.evaluation.validate_annotations
python -m app.evaluation.run
$env:MEDNLP_RUN_MODEL = "1"
python -m app.evaluation.run
```

The rule and model use the same six `synthetic_eval` documents. Exact spans require matching document ID, page, start/end offsets, and entity type. Lab value, unit, and reference interval exact-match metrics are conditional on strict-span matches. False-positive and false-negative examples, document classification metrics, per-entity scores, and source-span correctness are included in `evaluation.v2.json`. Version 1 outputs are retained as the earlier run; do not overwrite or treat them as the current implementation results.

The current machine used Python 3.11, `transformers==4.57.1`, and CPU PyTorch `2.9.1+cpu` from the optional local environment. `backend/requirements-model.txt` gives the direct optional dependencies; `backend/requirements-model-lock.txt` records the tested transitive closure. Model ID: `d4data/biomedical-ner-all`; immutable revision: `e2272cd5d96cb445524015fc5d9c1e198224a3bc`. Runtime/model cache are local and are not installed by core setup. The measured model has 66,427,476 parameters, a 512-position configuration, a fast `DistilBertTokenizerFast`, and runs on CPU. The current v2 run loaded in 67.64 seconds and took 0.70 seconds to infer across the six documents (0.117 seconds/document). This is one run on this machine, not a performance guarantee; the earlier v1 load/inference measurements describe a different run and implementation. RSS was not measured because optional `psutil` is not installed. First-time download and hardware will change load time and storage use.

| Baseline | Documents | Gold | TP | FP | FN | Precision | Recall | Strict-span F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rules v2 | 6 | 12 | 8 | 3 | 4 | 0.727 | 0.667 | 0.696 |
| Biomedical NER v2 | 6 | 12 | 0 | 17 | 12 | 0.000 | 0.000 | 0.000 |

Classification accuracy was 6/6 (1.000) on the four synthetic report-type labels. Source-span integrity was 11/11 for rule predictions and 17/17 for model predictions; this verifies offset grounding, not semantic correctness. The rule baseline's per-entity metrics and lab-attribute denominators are in the generated report. In this run, rules scored F1 0.750 for laboratory results, 0.500 for radiology findings, and 1.000 for diagnosis/symptom and medication spans. The separate radiology-impression candidate scored F1 0.000 (one false positive; no gold impression label in this split). The model's mapped classes all had zero true positives on these exact spans. Its output included fragmented entities (for example, parts of “lesion” and “ibuprofen”), lab-value spans without normalized values/units/ranges, and no matching radiology spans. These are descriptive examples from six synthetic documents, not general model quality conclusions.

## Model scope, label handling, and risks

The model card identifies an English DistilBERT token-classification NER model trained on MACCROBAT case reports and lists Apache-2.0 for the model repository. The pinned model revision is recorded above. This is the model license metadata only; it does not establish licenses for every dependency, the source dataset, or downstream material. Verify those separately for redistribution or commercial use. The model card describes biomedical NER and lists 107 biomedical entity categories; the loaded configuration exposes its label mapping in the machine-readable report.

The adapter maps only `Lab_value`, `Disease_disorder`, `Sign_symptom`, `Medication`, and `Diagnostic_procedure` to application types. It ignores other model labels. This narrow map does not make the model suitable for complete clinical extraction. It does not normalize lab values, attach units/reference intervals, or assess negation, uncertainty, and temporality. The library returns token scores, but this adapter discards them, so the app exposes no confidence. Do not treat token scores as calibrated confidence without separate validation.

The model's loaded config allows 512 positions. The adapter passes each page as one input and does not enable chunk/stride handling. A local 7,600-character input tokenized to 2,402 tokens emitted a Transformers overlength warning; predictions stopped at approximately character 1,610 of 7,600, confirming that the tail was omitted in this run. Long-page entities can therefore be silently missed. No recovery is implemented. Hugging Face's pipeline docs describe revision selection and pipeline behavior; this adapter intentionally pins a commit and uses its default token-classification pipeline settings.

The model was trained for English case reports, while this app handles laboratory tables, radiology and discharge notes, OCR text, and multiple report formats. Domain and layout mismatch, abbreviation variation, OCR artifacts, historical/negated findings, and class-boundary differences can cause false detections or omissions. The 0.000 strict F1 here demonstrates poor agreement with this particular small span protocol; it is not clinical validation.

References: [model card, task, dataset, and license](https://huggingface.co/d4data/biomedical-ner-all), [model configuration](https://huggingface.co/d4data/biomedical-ner-all/blob/e2272cd5d96cb445524015fc5d9c1e198224a3bc/config.json), [Transformers pipeline documentation](https://huggingface.co/docs/transformers/main_classes/pipelines).

## Summary review

`data/synthetic/summary_reviews.schema.json` defines source-linked review records; `data/synthetic/summary_reviews.v2.jsonl` contains three generated pending cases, one each from lab, radiology, and discharge examples. Each retains its source report and exact offset-checked passages. The current application summary consists of deterministic source-linked statements; candidate extracted claims are included for future human support/evidence review. All claim decisions, critical-omission decisions, contradiction decisions, and reviewer IDs are null/pending. No human review scores are claimed.

Regenerate and validate with:

```powershell
python -m app.evaluation.create_summary_review_set
python -m app.evaluation.validate_summary_reviews
```

The validator verifies source-page offsets and status consistency. Only completed rows with reviewer IDs contribute to rates; it prints counts and denominators. Currently 3 summaries are pending, 0 are reviewed, and every rate is null. A future reviewer can set `review_status` to `completed`, add a reviewer ID and adjudicate claims, evidence references, critical omissions, and contradictions. Application analyses now include structured patient-overview sections and explicit report-attributed differential possibilities, each source-linked to extracted evidence; these features have synthetic regression checks only.

The deterministic differential extractor has a synthetic smoke test over one authored three-page workup. It emits five separately attributed possibilities and links only explicitly labeled support/limiting passages. This is a parser regression check, not an evaluation score: the new differential fields do not yet have independently annotated development/validation/test splits, agreement measurements, precision/recall, or adjudicated evidence-link accuracy. Do not infer performance from the fixture count.

## Historical smoke data and future research

`data/synthetic/fixtures.json` and its former three-example smoke score are historical artifacts, not a held-out benchmark. Do not quote earlier metrics as evidence. For real-data evaluation, first obtain required governance, consent, and data/license approvals; define and independently apply an annotation protocol; split by patient and deduplicate before partitioning; freeze revisions/configuration; and report exclusions, failure modes, denominators, and uncertainty. Keep real-data outcomes separate from these synthetic regressions.
