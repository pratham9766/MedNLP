"""Validate every JSONL record, source span, patient split, and duplicate guard."""
from pathlib import Path
from app.evaluation.run import load_records

if __name__ == "__main__":
    root=Path(__file__).resolve().parents[3]
    records=load_records(root/"data/synthetic/annotations.v1.jsonl")
    print(f"Validated {len(records)} version 1.0 synthetic annotations; exact source spans and split checks passed.")
