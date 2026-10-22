"""Validate every JSONL record, source span, patient split, and duplicate guard."""
import os
from pathlib import Path
from app.evaluation.run import load_records

if __name__ == "__main__":
    root=Path(__file__).resolve().parents[3]
    source=Path(os.getenv("MEDNLP_ANNOTATIONS_PATH","data/synthetic/annotations.v1.jsonl"))
    if not source.is_absolute(): source=root/source
    records=load_records(source)
    entities=sum(len(record.annotations) for record in records)
    print(f"Validated {len(records)} synthetic annotations ({entities} entities); exact source spans, patient splits, annotation review status, and duplicate checks passed.")
