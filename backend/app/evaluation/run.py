"""Reproducible rule/model comparison on versioned authored synthetic annotations."""
import csv, json, os
from difflib import SequenceMatcher
from pathlib import Path
from app.evaluation.annotations import AnnotatedDocument
from app.evaluation.metrics import score_entities
from app.evaluation.model_adapter import BiomedicalNerAdapter
from app.nlp.extract import classify_document, process_pages
from app.schemas import PageText

def load_records(path):
    records=[AnnotatedDocument.model_validate_json(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids=set(); groups={}; texts={}
    for r in records:
        if r.document_id in ids: raise ValueError(f"duplicate document id {r.document_id}")
        ids.add(r.document_id); groups.setdefault(r.patient_group,set()).add(r.split)
        text="\n".join(p["text"] for p in r.pages).strip().casefold()
        if text:
            for prior,prior_split in texts.values():
                if prior_split!=r.split and SequenceMatcher(None,text,prior).ratio()>=0.92: raise ValueError(f"near duplicate split leakage: {r.document_id}")
            texts[r.document_id]=(text,r.split)
    if any(len(splits)>1 for splits in groups.values()): raise ValueError("patient group crosses split boundary")
    return records

def _gold(record):
    return [a.model_dump() for a in record.annotations]

def _rule(record):
    out=[]
    for page in record.pages:
        analysis=process_pages([PageText(page=page["page"],text=page["text"],extraction_method="synthetic")])
        for item in analysis.items:
            if item.span_start is None or item.span_end is None: continue
            out.append({"source_page":item.source_page,"start_char":item.span_start,"end_char":item.span_end,"entity_type":item.entity_type,"normalized_value":item.normalized_value,"unit":item.unit,"reference_interval":item.reference_interval,"negation":item.negated,"uncertainty":item.uncertain})
    return out

def _model(record, adapter):
    out=[]; states=[]
    for page in record.pages:
        predictions,state=adapter.predict(page["text"],page["page"]); out.extend(predictions); states.append(state)
    return out, states

def evaluate(records, run_model=False):
    held=[r for r in records if r.split=="synthetic_eval"]
    if not held: raise ValueError("no synthetic_eval documents are annotated")
    def baseline(predictor):
        gold=[]; predicted=[]; failures=[]; classified=0
        for record in held:
            gold.extend(_gold(record))
            try:
                pred=predictor(record); predicted.extend(pred)
                classified += classify_document("\n".join(p["text"] for p in record.pages))==record.document_type
            except Exception as exc: failures.append({"document_id":record.document_id,"error":f"{type(exc).__name__}: {exc}"})
        return {"document_count":len(held),"annotated_entity_count":len(gold),"document_type_correct":classified,"document_type_accuracy":classified/len(held),"processing_failures":failures,"processing_failure_count":len(failures),"unsupported_document_count":sum(r.document_type=="unknown" for r in held),"entity_metrics":score_entities(gold,predicted)}
    result={"schema_version":"1.0","dataset":"authored synthetic only; not clinical evidence","annotation_file":"data/synthetic/annotations.v1.jsonl","split":"synthetic_eval","patient_group_split_check":"passed","near_duplicate_cross_split_check":"passed","development_document_count":sum(r.split=="development" for r in records),"synthetic_eval_document_count":len(held),"rule_baseline":baseline(_rule),"pretrained_baseline":{"status":"not_run","model_id":os.getenv("MEDNLP_NER_MODEL","d4data/biomedical-ner-all"),"reason":"Set MEDNLP_RUN_MODEL=1 and install backend/requirements-model.txt to download and run weights."}}
    if run_model:
        adapter=BiomedicalNerAdapter(); state=adapter.load()
        result["pretrained_baseline"]={"status":state["status"],"model_id":state.get("model_id"),"model_revision":state.get("revision",adapter.revision)}
        if state["status"]!="available": result["pretrained_baseline"].update(state)
        else: result["pretrained_baseline"].update(baseline(lambda rec:_model(rec,adapter)[0]))
    return result

def write_outputs(result, root):
    out=root/"data/synthetic"; out.mkdir(parents=True,exist_ok=True)
    (out/"evaluation.v1.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    flat=[]
    for model in ("rule_baseline","pretrained_baseline"):
        metrics=result.get(model,{})
        em=metrics.get("entity_metrics",{})
        flat.append({"baseline":model,"status":metrics.get("status","available"),"documents":metrics.get("document_count"),"gold_entities":metrics.get("annotated_entity_count"),"precision":em.get("precision"),"recall":em.get("recall"),"strict_span_f1":em.get("strict_span_f1"),"processing_failures":metrics.get("processing_failure_count")})
    with (out/"evaluation.v1.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=flat[0]); writer.writeheader(); writer.writerows(flat)
    rule=result["rule_baseline"]; em=rule["entity_metrics"]
    value=em["lab_value_exact_match"]; unit=em["unit_accuracy"]; interval=em["reference_interval_accuracy"]; neg=em["negation_error_rate"]; unc=em["uncertainty_error_rate"]
    model_note=result["pretrained_baseline"].get("reason") or result["pretrained_baseline"].get("error") or ""
    md=["# Synthetic evaluation v1","","This is a small, manually labeled, authored synthetic set. It is not clinical evidence and does not estimate performance on real reports. The evaluation split is separate by synthetic patient group and checked for near duplicates; authorship is shared, so it is not an independent research benchmark.","",f"- Development documents: {result['development_document_count']}",f"- Synthetic evaluation documents: {result['synthetic_eval_document_count']}",f"- Labeled entities: {rule['annotated_entity_count']}",f"- Rule document-type accuracy: {rule['document_type_correct']}/{rule['document_count']} ({rule['document_type_accuracy']:.3f})",f"- Strict entity spans: TP {em['true_positive']}, FP {em['false_positive']}, FN {em['false_negative']}",f"- Precision {em['precision']:.3f}; recall {em['recall']:.3f}; strict-span F1 {em['strict_span_f1']:.3f}",f"- Lab value exact-match accuracy: {value['correct']}/{value['count']} ({value['accuracy']:.3f})" if value['accuracy'] is not None else "- Lab value exact-match accuracy: not measured",f"- Unit accuracy: {unit['correct']}/{unit['count']} ({unit['accuracy']:.3f})" if unit['accuracy'] is not None else "- Unit accuracy: not measured",f"- Reference interval accuracy: {interval['correct']}/{interval['count']} ({interval['accuracy']:.3f})" if interval['accuracy'] is not None else "- Reference interval accuracy: not measured",f"- Negation error rate: {neg['errors']}/{neg['count']} ({neg['rate']:.3f})" if neg['rate'] is not None else "- Negation error rate: not measured",f"- Uncertainty error rate: {unc['errors']}/{unc['count']} ({unc['rate']:.3f})" if unc['rate'] is not None else "- Uncertainty error rate: not measured",f"- Processing failures: {rule['processing_failure_count']}; unsupported docs: {rule['unsupported_document_count']}",f"- Pretrained baseline: {result['pretrained_baseline']['status']} — {model_note}","","Small denominator results are descriptive regression measurements only. No confidence or clinical performance claim is made."]
    (out/"evaluation.v1.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":
    root=Path(__file__).resolve().parents[3]
    source=root/"data/synthetic/annotations.v1.jsonl"
    result=evaluate(load_records(source),run_model=os.getenv("MEDNLP_RUN_MODEL")=="1")
    write_outputs(result,root)
    print(json.dumps(result,indent=2))
