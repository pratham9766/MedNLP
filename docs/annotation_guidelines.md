# Synthetic annotation format

`data/synthetic/fixtures.json` uses records with `id`, `document_type`, `text`, and `expected_entities`. Each entity includes a type and exact original source span. Page numbers in manually labeled multi-page fixtures are one-based. Annotators should preserve spelling and OCR ambiguity exactly, label negation and uncertainty in context, distinguish historical mentions from current findings, and never create a value or reference interval absent from the source. Keep all fixture data synthetic and avoid any identifiers derived from real records.
