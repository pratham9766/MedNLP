# Human review checklist for synthetic demonstration summaries

This checklist is for a qualified reviewer assessing the three records in `data/synthetic/summary_reviews.v2.jsonl`. Every included case is synthetic. The records remain pending until a reviewer completes them; do not treat automated scores or project-team annotations as human review.

## For each case

- [ ] Confirm the source report and page numbers match the rendered/source text.
- [ ] For every claim, mark whether it is directly supported by the quoted source passage.
- [ ] Confirm each evidence reference points to the exact passage and does not omit a qualifier that changes meaning.
- [ ] Check negation and uncertainty (for example, “no acute” versus “cannot exclude”).
- [ ] Check temporality (current finding versus prior history or unchanged old finding).
- [ ] Check that a possibility or differential is not presented as a confirmed diagnosis.
- [ ] Check that values, units, flags, and reference intervals are preserved as printed; flag any OCR ambiguity.
- [ ] Record any clinically important omission and whether the summary contradicts the source.
- [ ] Record reviewer identifier and completion status only after the entire case has been reviewed.

## Adjudication fields

In each record, set `review_status` to `completed`, `reviewed` to `true`, and `reviewer_id` to the reviewer’s approved identifier only after completing the review. For each claim, set `supported` and `evidence_correct` to `true` or `false`; do not use a guess to fill a decision. Set `critical_omission` and `contradiction` to booleans after considering the whole report. Leave undecided fields `null` and the record pending until adjudicated.

The records are data artifacts and should only be edited by an authorized human reviewer. The evaluation script counts completed, explicitly reviewed records and reports denominators; pending rows do not contribute to rates.
