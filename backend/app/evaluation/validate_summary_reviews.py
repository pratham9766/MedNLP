"""Validate source-linked summary review rows and report only adjudicated rates."""
import json
from pathlib import Path
from app.evaluation.metrics import summarize_review

FIELDS={"schema_version","document_id","source_report","generated_summary","review_status","reviewed","claims","critical_omission","contradiction","reviewer_id"}
CLAIM_FIELDS={"claim","supported","evidence_correct","source_page","start_char","end_char"}

def validate_record(row):
    if set(row)!=FIELDS: raise ValueError(f"{row.get('document_id','?')}: invalid record fields")
    if row["schema_version"]!="2.0" or row["review_status"] not in ("pending","completed"):
        raise ValueError(f"{row.get('document_id','?')}: unsupported version or review status")
    completed=row["review_status"]=="completed"
    if row["reviewed"] is not completed: raise ValueError("reviewed must agree with review_status")
    if completed and (not isinstance(row["reviewer_id"],str) or not row["reviewer_id"].strip()): raise ValueError("completed review requires reviewer_id")
    if not completed and row["reviewer_id"] is not None: raise ValueError("pending review must not claim a reviewer")
    pages={p["page"]:p["text"] for p in row["source_report"]["pages"]}
    for passage in row["source_report"]["passages"]:
        text=pages.get(passage["page"])
        if text is None or text[passage["start_char"]:passage["end_char"]]!=passage["quote"]: raise ValueError("source passage offsets do not match source report")
    for claim in row["claims"]:
        if set(claim)!=CLAIM_FIELDS: raise ValueError("invalid claim fields")
        if not completed and any(claim.get(k) is not None for k in ("supported","evidence_correct")): raise ValueError("pending claims cannot have human scores")
        if completed and any(not isinstance(claim.get(k),bool) for k in ("supported","evidence_correct")): raise ValueError("completed claims require support and evidence decisions")
        offsets=(claim.get("source_page"),claim.get("start_char"),claim.get("end_char"))
        if any(v is not None for v in offsets):
            page,start,end=offsets
            if None in offsets or page not in pages or start<0 or end<=start or pages[page][start:end]!=claim["claim"]: raise ValueError("claim evidence span does not match source report")
    if not completed and (row["critical_omission"] is not None or row["contradiction"] is not None): raise ValueError("pending summary cannot have review scores")
    if completed and (not isinstance(row["critical_omission"],bool) or not isinstance(row["contradiction"],bool)): raise ValueError("completed summary requires omission and contradiction decisions")

def load(path):
    rows=[json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    ids=[r.get("document_id") for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate summary review document_id")
    for row in rows: validate_record(row)
    return rows

if __name__=="__main__":
    root=Path(__file__).resolve().parents[3]
    rows=load(root/"data/synthetic/summary_reviews.v2.jsonl")
    print(json.dumps(summarize_review(rows),indent=2))
