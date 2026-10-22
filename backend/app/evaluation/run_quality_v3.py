"""Create the v3 held-out comparison against the frozen pre-change rule output."""
import json
import os
from pathlib import Path

from app.evaluation.run import evaluate, load_records, write_outputs

ROOT = Path(__file__).resolve().parents[3]
ANNOTATIONS = ROOT / "data/synthetic/annotations.v2.jsonl"
BASELINE = ROOT / "data/synthetic/evaluation.v3-baseline.json"


def main():
    records = load_records(ANNOTATIONS)
    before = json.loads(BASELINE.read_text(encoding="utf-8"))
    unchanged = before["rule_baseline"]
    if unchanged.get("entity_metrics"):
        unchanged["unmatched_prediction_count"] = unchanged["entity_metrics"]["false_positive"]
    result = evaluate(records, run_model=False)
    result["annotation_file"] = "data/synthetic/annotations.v2.jsonl"
    result["unchanged_rules_baseline"] = unchanged
    result["pretrained_baseline"] = {
        "status": "not_run",
        "model_id": before.get("pretrained_baseline", {}).get("model_id"),
        "model_revision": before.get("pretrained_baseline", {}).get("model_revision"),
        "reason": "Optional pretrained inference was not requested; no pretrained score is reported.",
    }
    result["comparison_policy"] = (
        "Same frozen synthetic_eval annotations and extraction code before/after; "
        "development annotations were expanded before tuning, with the held-out set frozen."
    )
    write_outputs(result, ROOT, version=os.getenv("MEDNLP_EVALUATION_VERSION", "v3"))
    print(json.dumps({
        "dataset": result["annotation_file"],
        "heldout_documents": result["synthetic_eval_document_count"],
        "unchanged_rules": result["unchanged_rules_baseline"].get("entity_metrics"),
        "improved_rules": result["rule_baseline"].get("entity_metrics"),
        "classification": result["classification_metrics"],
        "model_status": result["pretrained_baseline"]["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
