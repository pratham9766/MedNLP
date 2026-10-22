"""Reproducible rule/model comparison on versioned authored synthetic annotations."""
import csv, json, os, time
from difflib import SequenceMatcher
from pathlib import Path
from app.evaluation.annotations import AnnotatedDocument
from app.evaluation.metrics import score_entities, score_relations
from app.evaluation.model_adapter import BiomedicalNerAdapter, DEFAULT_MODEL, DEFAULT_REVISION
from app.nlp.extract import classify_document, process_pages
from app.schemas import PageText

DOC_TYPES=("laboratory","discharge","radiology","unknown")

def load_records(path):
    records=[AnnotatedDocument.model_validate_json(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids=set(); groups={}; texts={}
    for record in records:
        if record.document_id in ids: raise ValueError(f"duplicate document id {record.document_id}")
        ids.add(record.document_id); groups.setdefault(record.patient_group,set()).add(record.split)
        text=" ".join("\n".join(page["text"] for page in record.pages).casefold().split())
        if text:
            for prior,prior_id,prior_split in texts.values():
                if SequenceMatcher(None,text,prior).ratio()>=0.92:
                    boundary="cross-split leakage" if prior_split!=record.split else "duplicate within split"
                    raise ValueError(f"{boundary}: {prior_id} and {record.document_id}")
            texts[record.document_id]=(text,record.document_id,record.split)
    if any(len(splits)>1 for splits in groups.values()): raise ValueError("patient group crosses split boundary")
    return records

def _gold(record):
    return [{**annotation.model_dump(),"document_id":record.document_id,"document_type":record.document_type} for annotation in record.annotations]

def _rule(record):
    analysis=process_pages([PageText(page=page["page"],text=page["text"],extraction_method="synthetic") for page in record.pages])
    status_by_item={possibility.source_evidence_ids[0]:possibility.assertion_status for possibility in analysis.differential_possibilities if possibility.source_evidence_ids}
    relations_by_item={}
    for possibility in analysis.differential_possibilities:
        if not possibility.source_evidence_ids: continue
        target=possibility.source_evidence_ids[0]
        for source in possibility.evidence_for: relations_by_item.setdefault(source,[]).append({"relation_type":"supports","target_entity_id":target})
        for source in possibility.evidence_against: relations_by_item.setdefault(source,[]).append({"relation_type":"limits","target_entity_id":target})
    return [{"document_id":record.document_id,"document_type":record.document_type,"entity_id":item.id,"source_page":item.source_page,"start_char":item.span_start,"end_char":item.span_end,"entity_type":item.entity_type,"original_text":item.original_text,"normalized_value":item.normalized_value,"unit":item.unit,"reference_interval":item.reference_interval,"negation":item.negated,"uncertainty":item.uncertain,"temporality":item.temporality,"assertion_status":status_by_item.get(item.id),"medication_name":item.medication_name,"dose":item.dose,"route":item.route,"frequency":item.frequency,"duration":getattr(item,"duration",None),"medication_change":getattr(item,"medication_change",None),"relations":relations_by_item.get(item.id,[])} for item in analysis.items if item.span_start is not None and item.span_end is not None]

def _model(record, adapter):
    out=[]
    for page in record.pages:
        predictions,state=adapter.predict(page["text"],page["page"])
        if state.get("status")!="available": raise RuntimeError(state.get("error",state.get("status","model inference failed")))
        out.extend({**prediction,"document_id":record.document_id,"document_type":record.document_type} for prediction in predictions)
    return out

def _classification_metrics(records):
    matrix={actual:{predicted:0 for predicted in DOC_TYPES} for actual in DOC_TYPES}
    predictions={record.document_id:classify_document("\n".join(page["text"] for page in record.pages)) for record in records}
    for record in records: matrix[record.document_type][predictions[record.document_id]]+=1
    per_type={}
    for label in DOC_TYPES:
        tp=matrix[label][label]; fp=sum(matrix[actual][label] for actual in DOC_TYPES if actual!=label); fn=sum(matrix[label][predicted] for predicted in DOC_TYPES if predicted!=label)
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
        per_type[label]={"true_positive":tp,"false_positive":fp,"false_negative":fn,"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0.0}
    correct=sum(matrix[label][label] for label in DOC_TYPES); total=len(records)
    return {"correct":correct,"count":total,"accuracy":correct/total if total else None,"confusion_matrix":matrix,"per_type":per_type}

def _evidence_span_correctness(records,predictions):
    pages={record.document_id:{page["page"]:page["text"] for page in record.pages} for record in records}
    correct=0; resolved=0
    for prediction in predictions:
        doc_id=prediction.get("document_id"); page=prediction.get("source_page"); start=prediction.get("start_char"); end=prediction.get("end_char")
        if doc_id in pages and page in pages[doc_id] and isinstance(start,int) and isinstance(end,int) and end>start:
            resolved+=1
            correct+=pages[doc_id][page][start:end]==prediction.get("original_text")
    return {"correct":correct,"count":len(predictions),"resolved_span_count":resolved,"unresolved_span_count":len(predictions)-resolved,"accuracy":correct/len(predictions) if predictions else None}

def evaluate(records,run_model=False):
    held=[record for record in records if record.split=="synthetic_eval"]
    if not held: raise ValueError("no synthetic_eval documents are annotated")
    def baseline(predictor):
        gold=[]; predicted=[]; failures=[]
        for record in held:
            gold.extend(_gold(record))
            try: predicted.extend(predictor(record))
            except Exception as exc: failures.append({"document_id":record.document_id,"error":f"{type(exc).__name__}: {exc}"})
        result={"status":"available" if not failures else "partial_failure","document_count":len(held),"annotated_entity_count":len(gold),"prediction_count":len(predicted),"unsupported_document_count":sum(record.document_type=="unknown" for record in held),"processing_failures":failures,"processing_failure_count":len(failures),"predictions":predicted}
        if not failures:
            result["evidence_span_correctness"]=_evidence_span_correctness(held,predicted)
            result["entity_metrics"]=score_entities(gold,predicted)
            # Operationally, these are predictions without an exact gold span.
            # They are not a human judgment that the source claim is unsupported.
            result["unmatched_prediction_count"]=result["entity_metrics"]["false_positive"]
            result["evidence_link_metrics"]=score_relations(gold,predicted)
        return result
    result={"schema_version":"3.0","dataset":"authored synthetic only; not clinical evidence","annotation_file":"data/synthetic/annotations.v2.jsonl","annotation_review_status_counts":{status:sum(record.annotation_review_status==status for record in records) for status in sorted({record.annotation_review_status for record in records})},"split":"synthetic_eval","offset_policy":"exact source-text offsets; Unicode text is not normalized; zero-based, end-exclusive Python string indices, page-relative","patient_group_split_check":"passed","near_duplicate_check":{"method":"case-folded, whitespace-collapsed SequenceMatcher ratio","threshold":0.92,"scope":"all document pairs, including within a split"},"development_document_count":sum(record.split=="development" for record in records),"synthetic_eval_document_count":len(held),"classification_metrics":_classification_metrics(held),"rule_baseline":baseline(_rule),"pretrained_baseline":{"status":"not_run","model_id":os.getenv("MEDNLP_NER_MODEL",DEFAULT_MODEL),"model_revision":os.getenv("MEDNLP_NER_REVISION",DEFAULT_REVISION),"reason":"Optional pretrained inference was not requested; no pretrained score is reported."}}
    if run_model:
        adapter=BiomedicalNerAdapter(); state=adapter.load()
        model={"status":"not_run","model_id":state.get("model_id",adapter.model_id),"model_revision":state.get("revision",adapter.revision),"model_load_seconds":state.get("load_seconds")}
        if state["status"]!="available": model.update({"reason":f"Model load unavailable: {state.get('error','unknown load error')}","availability":"unavailable"})
        else:
            started=time.perf_counter(); model.update(baseline(lambda record:_model(record,adapter)))
            elapsed=time.perf_counter()-started
            if model["status"]=="available":
                model["inference_seconds_total"]=elapsed; model["inference_seconds_per_document"]=elapsed/len(held)
                try:
                    import psutil
                    model["process_rss_bytes_after_inference"]=psutil.Process().memory_info().rss
                except ImportError: model["process_rss_bytes_after_inference"]="unavailable (psutil not installed)"
                model.update({key:value for key,value in state.items() if key!="status"})
            else:
                model={"status":"not_run","model_id":state.get("model_id",adapter.model_id),"model_revision":state.get("revision",adapter.revision),"reason":"Inference failed for at least one held-out document; a partial or zero score is not reported.","processing_failures":model["processing_failures"],"processing_failure_count":model["processing_failure_count"]}
        result["pretrained_baseline"]=model
    return result

def write_outputs(result,root,version="v2"):
    out=root/"data/synthetic"; out.mkdir(parents=True,exist_ok=True)
    (out/f"evaluation.{version}.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    flat=[]
    for name in ("unchanged_rules_baseline","rule_baseline","pretrained_baseline"):
        metrics=result.get(name,{}); entity=metrics.get("entity_metrics",{})
        flat.append({"baseline":name,"status":metrics.get("status","available"),"documents":metrics.get("document_count"),"gold_entities":metrics.get("annotated_entity_count"),"precision":entity.get("precision"),"recall":entity.get("recall"),"strict_span_f1":entity.get("strict_span_f1"),"evidence_span_accuracy":metrics.get("evidence_span_correctness",{}).get("accuracy"),"processing_failures":metrics.get("processing_failure_count")})
    with (out/f"evaluation.{version}.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(flat[0])); writer.writeheader(); writer.writerows(flat)
    rules=result["rule_baseline"]; model=result["pretrained_baseline"]
    md=[f"# Synthetic evaluation {version}","","Project-team-authored synthetic regression results only. No independent annotation, adjudication, clinical validation, or real-world performance estimate is available.","",f"- Dataset: `{result['annotation_file']}`",f"- Development documents: {result['development_document_count']}",f"- Held-out synthetic evaluation documents: {result['synthetic_eval_document_count']}",f"- Exact span convention: {result['offset_policy']}",f"- Duplicate guard: {result['near_duplicate_check']}","", "## Baseline comparison", "", "| Baseline | Status | Documents | Gold annotations | Predictions | TP | FP | FN | Precision | Recall | Strict-span F1 | Source-span integrity |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    comparisons=[]
    if result.get("unchanged_rules_baseline"):
        comparisons.append(("Rules (unchanged)",result["unchanged_rules_baseline"]))
    comparisons.extend((("Rules (improved)",rules),(model.get("model_id","Pretrained"),model)))
    for label,metrics in comparisons:
        scores=metrics.get("entity_metrics",{}); span=metrics.get("evidence_span_correctness",{})
        fmt=lambda value: f"{value:.3f}" if isinstance(value,(int,float)) else "—"
        integrity=f"{span.get('correct')}/{span.get('count')} ({fmt(span.get('accuracy'))})" if span else "—"
        md.append(f"| {label} | {metrics.get('status','not_run')} | {metrics.get('document_count','—')} | {metrics.get('annotated_entity_count','—')} | {metrics.get('prediction_count','—')} | {scores.get('true_positive','—')} | {scores.get('false_positive','—')} | {scores.get('false_negative','—')} | {fmt(scores.get('precision'))} | {fmt(scores.get('recall'))} | {fmt(scores.get('strict_span_f1'))} | {integrity} |")
        if metrics.get("status")!="available" and metrics.get("reason"):
            md.append(""); md.append(f"{label} result: {metrics['reason']}")
    metrics=rules.get("entity_metrics")
    if metrics:
        md += ["", "## Entity results by type", "", "| Entity type | TP | FP | FN | Precision | Recall | Strict-span F1 |", "|---|---:|---:|---:|---:|---:|---:|"]
        for typ,stats in metrics["per_entity"].items(): md.append(f"| {typ} | {stats['true_positive']} | {stats['false_positive']} | {stats['false_negative']} | {stats['precision']:.3f} | {stats['recall']:.3f} | {stats['strict_span_f1']:.3f} |")
        md += ["", "## Entity results by report type", "", "| Report type | TP | FP | FN | Precision | Recall | Strict-span F1 |", "|---|---:|---:|---:|---:|---:|---:|"]
        for typ,stats in metrics["per_document_type"].items(): md.append(f"| {typ} | {stats['true_positive']} | {stats['false_positive']} | {stats['false_negative']} | {stats['precision']:.3f} | {stats['recall']:.3f} | {stats['strict_span_f1']:.3f} |")
        md += ["", "## Context and extraction attributes", "", "| Attribute | Correct | Eligible exact-span matches | Unavailable attribute | Accuracy |", "|---|---:|---:|---:|---:|"]
        for field,stats in metrics["attribute_classification"].items(): md.append(f"| {field} | {stats['correct']} | {stats['count']} | {stats['unavailable_on_matched_spans']} | {stats['accuracy'] if stats['accuracy'] is not None else '—'} |")
        md += ["", "## Medications", "", "| Field | Correct | Matched medication spans with both values | Gold values present | Exact-match accuracy |", "|---|---:|---:|---:|---:|"]
        for field,stats in metrics["medication_fields"].items(): md.append(f"| {field} | {stats['correct']} | {stats['count']} | {stats['annotated_count']} | {stats['accuracy'] if stats['accuracy'] is not None else '—'} |")
        md += ["", "## Document classification", "", f"- Accuracy: {result['classification_metrics']['correct']}/{result['classification_metrics']['count']} ({result['classification_metrics']['accuracy']:.3f})", "", "| Report type | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
        for label,stats in result["classification_metrics"]["per_type"].items(): md.append(f"| {label} | {stats['precision']:.3f} | {stats['recall']:.3f} | {stats['f1']:.3f} |")
        md += ["", "## Errors and limits", "", f"- Rule processing failures: {rules['processing_failure_count']}",f"- Unsupported/unknown-type documents: {rules['unsupported_document_count']}",f"- Unmatched predictions (strict-span false positives): {rules.get('unmatched_prediction_count','—')}","- An unmatched prediction is an exact-span metric error, not a human adjudication that the source claim is unsupported.",f"- Model status: {model['status']}",f"- Model reason: {model.get('reason','—')}","- Attribute metrics apply only to strict-span matches where both annotation and predictor supplied the attribute.","- Source-span integrity confirms offsets resolve to original source text. It does not establish semantic correctness or that a linked passage supports a claim.","- Results are preliminary because the corpus is small, synthetic, and not independently reviewed."]
        links=rules.get("evidence_link_metrics",{})
        md += ["", "## Differential evidence links", "",f"- Exact linked evidence count: {links.get('true_positive','—')} correct / {links.get('annotated_link_count','—')} annotated; predicted {links.get('predicted_link_count','—')}; precision {links.get('precision','—')}, recall {links.get('recall','—')}, F1 {links.get('f1','—')}.",f"- Interpretation: {links.get('interpretation','unavailable')}"]
    (out/f"evaluation.{version}.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":
    root=Path(__file__).resolve().parents[3]
    annotation_path=Path(os.getenv("MEDNLP_ANNOTATIONS_PATH","data/synthetic/annotations.v1.jsonl"))
    if not annotation_path.is_absolute(): annotation_path=root/annotation_path
    records=load_records(annotation_path)
    result=evaluate(records,run_model=os.getenv("MEDNLP_RUN_MODEL")=="1"); result["annotation_file"]=str(annotation_path.relative_to(root)) if root in annotation_path.parents else annotation_path.name
    write_outputs(result,root,version=os.getenv("MEDNLP_EVALUATION_VERSION","v2")); print(json.dumps({key:value for key,value in result.items() if key not in {"rule_baseline"}},indent=2))
