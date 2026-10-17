"""Small reproducible fixture evaluator; metrics describe only this synthetic fixture set."""
import json, re
from pathlib import Path
from app.nlp.extract import classify_document, process_pages
from app.schemas import PageText

def score(fixtures):
    gold=[x["document_type"] for x in fixtures]; pred=[classify_document(x["text"]) for x in fixtures]
    labels=sorted(set(gold)|set(pred)); accuracy=sum(a==b for a,b in zip(gold,pred))/max(1,len(gold))
    f1=[]
    for label in labels:
        tp=sum(a==label and b==label for a,b in zip(gold,pred)); fp=sum(a!=label and b==label for a,b in zip(gold,pred)); fn=sum(a==label and b!=label for a,b in zip(gold,pred))
        p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0; f1.append(2*p*r/(p+r) if p+r else 0)
    exact=[]
    for f in fixtures:
        if f["expected_entities"]:
            result=process_pages([PageText(page=1,text=f["text"],extraction_method="fixture")])
            got={re.sub(r"\s+"," ",i.original_text.strip()).lower() for i in result.items}
            want={re.sub(r"\s+"," ",i["original_text"].strip()).lower() for i in f["expected_entities"]}
            exact.append(len(got & want)/max(1,len(want)))
    return {"fixture_count":len(fixtures),"document_classification_accuracy":accuracy,"document_classification_macro_f1":sum(f1)/max(1,len(f1)),"lab_entity_exact_match_on_labeled_fixtures":sum(exact)/max(1,len(exact)),"status":"synthetic smoke evaluation only; not clinical evidence","unsupported_metrics":["biomedical-model baseline","span precision/recall","summary support/omission","QA correctness/support","OCR CER/WER","reliability categories"]}

if __name__=="__main__":
    root=Path(__file__).resolve().parents[3]
    data=json.loads((root/"data/synthetic/fixtures.json").read_text(encoding="utf-8"))
    out=score(data); path=root/"data/synthetic/evaluation.json"; path.write_text(json.dumps(out,indent=2),encoding="utf-8"); print(json.dumps(out,indent=2))
