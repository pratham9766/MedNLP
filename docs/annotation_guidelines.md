# Synthetic annotation guidelines

Use `data/synthetic/annotations.v1.jsonl` and the Pydantic schema in `backend/app/evaluation/annotations.py`.

- Create synthetic documents only; never paste protected or identifiable clinical data into this regression set.
- Offsets are zero-based, end-exclusive, and relative to the exact text of the one-based source page. `original_text` must equal the sliced page text exactly.
- Preserve OCR errors, casing, punctuation, whitespace, and wording in `original_text`. Do not silently fix uncertain `O`/`0` or `I`/`1` characters.
- Use normalized values only when normalization is unambiguous from the text. Capture unit and interval only when stated.
- Annotate negation, uncertainty, and historical/current context conservatively. A suspected or possible finding is not confirmed; a historical diagnosis is not current.
- Use relations only when a relation is explicit and link to another entity ID. Provenance must identify the annotation source.
- Empty or unsupported docs retain the document record and an empty `annotations` list.
- Patient groups stay wholly within one split. Keep exact and near duplicates in one split.

Validate with `python -m app.evaluation.validate_annotations` from `backend`.
