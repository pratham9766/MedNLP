"""Create pending review cases from fixed synthetic annotation examples."""
import json
from pathlib import Path
from app.evaluation.run import load_records
from app.nlp.extract import generate_grounded_summary, process_pages
from app.schemas import PageText

EXAMPLE_IDS = ("eval-lab-01", "eval-rad-01", "eval-dis-01")

def create(source: Path, output: Path):
    records={r.document_id:r for r in load_records(source)}
    result=[]
    for document_id in EXAMPLE_IDS:
        record=records[document_id]
        pages=[PageText(page=p["page"],text=p["text"],extraction_method="synthetic_authored") for p in record.pages]
        analysis=process_pages(pages)
        passages=[{"page":item.source_page,"start_char":item.span_start,"end_char":item.span_end,"quote":item.original_text} for item in analysis.items if item.span_start is not None and item.span_end is not None]
        claims=[{"claim":item.original_text,"supported":None,"evidence_correct":None,"source_page":item.source_page,"start_char":item.span_start,"end_char":item.span_end} for item in analysis.items if item.span_start is not None and item.span_end is not None]
        result.append({"schema_version":"2.0","document_id":document_id,"source_report":{"pages":[{"page":p.page,"text":p.text} for p in pages],"passages":passages},"generated_summary":generate_grounded_summary(analysis),"review_status":"pending","reviewed":False,"claims":claims,"critical_omission":None,"contradiction":None,"reviewer_id":None})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in result),encoding="utf-8")
    return result

if __name__=="__main__":
    root=Path(__file__).resolve().parents[3]
    rows=create(root/"data/synthetic/annotations.v1.jsonl",root/"data/synthetic/summary_reviews.v2.jsonl")
    print(f"Created {len(rows)} pending synthetic summary reviews; no human scores assigned.")
