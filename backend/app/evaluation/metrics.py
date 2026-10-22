"""Exact source-span and matched-span attribute metrics.

Offsets are zero-based, end-exclusive Python string indices into the original
page text. No text normalization is applied to offsets or span identity.
"""
from collections import Counter, defaultdict


def _key(item):
    return (item.get("document_id", ""), item["source_page"], item["start_char"], item["end_char"], item["entity_type"])


def _counts(gold, predicted):
    gold_counts=Counter(_key(item) for item in gold)
    predicted_counts=Counter(_key(item) for item in predicted)
    tp=sum(min(count,predicted_counts[key]) for key,count in gold_counts.items())
    fp=len(predicted)-tp
    fn=len(gold)-tp
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    return {"true_positive":tp,"false_positive":fp,"false_negative":fn,"precision":precision,"recall":recall,"strict_span_f1":2*precision*recall/(precision+recall) if precision+recall else 0.0}


def _matched_pairs(gold, predicted):
    gold_by_key=defaultdict(list); predicted_by_key=defaultdict(list)
    for item in gold: gold_by_key[_key(item)].append(item)
    for item in predicted: predicted_by_key[_key(item)].append(item)
    return [(g,p) for key in gold_by_key.keys() & predicted_by_key.keys() for g,p in zip(gold_by_key[key],predicted_by_key[key])]


def _unmatched(gold, predicted):
    gold_by_key=defaultdict(list); predicted_by_key=defaultdict(list)
    for item in gold: gold_by_key[_key(item)].append(item)
    for item in predicted: predicted_by_key[_key(item)].append(item)
    false_positive=[item for key,items in predicted_by_key.items() for item in items[len(gold_by_key[key]):]]
    false_negative=[item for key,items in gold_by_key.items() for item in items[len(predicted_by_key[key]):]]
    return false_positive[:20],false_negative[:20]


def _classification(field, pairs):
    eligible=[(g.get(field),p.get(field)) for g,p in pairs if g.get(field) is not None and p.get(field) is not None]
    labels=sorted({value for pair in eligible for value in pair},key=str)
    confusion={str(actual):{str(predicted):0 for predicted in labels} for actual in labels}
    for actual,predicted in eligible: confusion[str(actual)][str(predicted)]+=1
    correct=sum(actual==predicted for actual,predicted in eligible)
    per_class={}
    for label in labels:
        tp=confusion[str(label)][str(label)]
        fp=sum(confusion[str(actual)][str(label)] for actual in labels if actual!=label)
        fn=sum(confusion[str(label)][str(predicted)] for predicted in labels if predicted!=label)
        per_class[str(label)]={"support":sum(confusion[str(label)].values()),"precision":tp/(tp+fp) if tp+fp else None,"recall":tp/(tp+fn) if tp+fn else None,"f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
    return {"correct":correct,"count":len(eligible),"unavailable_on_matched_spans":len(pairs)-len(eligible),"accuracy":correct/len(eligible) if eligible else None,"confusion_matrix":confusion,"per_class":per_class}


def _field_accuracy(field, pairs):
    eligible=[(g.get(field),p.get(field)) for g,p in pairs if g.get(field) is not None and p.get(field) is not None]
    expected=sum(g.get(field) is not None for g,_ in pairs)
    correct=sum(g==p for g,p in eligible)
    return {"correct":correct,"count":len(eligible),"annotated_count":expected,"prediction_available_count":len(eligible),"accuracy":correct/len(eligible) if eligible else None}


def score_relations(gold, predicted):
    """Score explicit evidence-to-possibility links with exact span endpoints."""
    def edges(rows):
        ids={item.get("entity_id"): _key(item) for item in rows if item.get("entity_id")}
        found=[]
        for item in rows:
            for relation in item.get("relations",[]):
                target_id=relation.get("target_entity_id")
                target=ids.get(target_id)
                # Keep malformed/unresolved predictions in the denominator as
                # impossible-to-match edges instead of silently dropping them.
                if target is None:
                    target=("unresolved_target",item.get("document_id",""),target_id)
                found.append((_key(item),relation.get("relation_type"),target))
        return Counter(found)
    g=edges(gold); p=edges(predicted)
    tp=sum(min(count,p[key]) for key,count in g.items())
    fp=sum(p.values())-tp; fn=sum(g.values())-tp
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    return {"true_positive":tp,"false_positive":fp,"false_negative":fn,"annotated_link_count":sum(g.values()),"predicted_link_count":sum(p.values()),"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else None,"interpretation":"Exact evidence-item and differential-possibility span endpoints plus relation label; preliminary synthetic labels."}


def score_entities(gold, predicted):
    """Score a multiset of exact spans; duplicate predictions remain false positives."""
    overall=_counts(gold,predicted)
    per_type={}
    for typ in sorted({x["entity_type"] for x in gold+predicted}):
        per_type[typ]=_counts([x for x in gold if x["entity_type"]==typ],[x for x in predicted if x["entity_type"]==typ])
    by_document_type={}
    for kind in sorted({x.get("document_type","unknown") for x in gold+predicted}):
        by_document_type[kind]=_counts([x for x in gold if x.get("document_type","unknown")==kind],[x for x in predicted if x.get("document_type","unknown")==kind])
    matches=_matched_pairs(gold,predicted)
    lab=[(g,p) for g,p in matches if g["entity_type"]=="laboratory_result"]
    attrs={field:_classification(field,matches) for field in ("negation","uncertainty","temporality")}
    attrs["assertion_status"]=_classification("assertion_status",[(g,p) for g,p in matches if g["entity_type"]=="differential_possibility"])
    medication=[(g,p) for g,p in matches if g["entity_type"]=="medication"]
    false_positive_examples,false_negative_examples=_unmatched(gold,predicted)
    return {**overall,"prediction_count":len(predicted),"annotation_count":len(gold),"per_entity":per_type,"per_document_type":by_document_type,
      "attribute_classification":attrs,
      "negation_error_rate":{"errors":attrs["negation"]["count"]-attrs["negation"]["correct"],"count":attrs["negation"]["count"],"rate":1-attrs["negation"]["accuracy"] if attrs["negation"]["accuracy"] is not None else None},
      "uncertainty_error_rate":{"errors":attrs["uncertainty"]["count"]-attrs["uncertainty"]["correct"],"count":attrs["uncertainty"]["count"],"rate":1-attrs["uncertainty"]["accuracy"] if attrs["uncertainty"]["accuracy"] is not None else None},
      "temporality_error_rate":{"errors":attrs["temporality"]["count"]-attrs["temporality"]["correct"],"count":attrs["temporality"]["count"],"rate":1-attrs["temporality"]["accuracy"] if attrs["temporality"]["accuracy"] is not None else None},
      "lab_value_exact_match":_field_accuracy("normalized_value",lab),"unit_accuracy":_field_accuracy("unit",lab),"reference_interval_accuracy":_field_accuracy("reference_interval",lab),
      "medication_fields":{field:_field_accuracy(field,medication) for field in ("medication_name","dose","route","frequency","duration","medication_change")},
      "false_positive_examples":false_positive_examples,"false_negative_examples":false_negative_examples}

def summarize_review(records):
    """Only completed human reviews enter score denominators; counts include pending items."""
    reviewed=[r for r in records if r.get("review_status", "completed" if r.get("reviewed") else "pending")=="completed" and r.get("reviewed") is True]
    n=len(reviewed)
    claims=[c for r in reviewed for c in r.get("claims",[])]
    return {"summary_count":len(records),"pending_summary_count":sum(r.get("review_status", "completed" if r.get("reviewed") else "pending")=="pending" for r in records),"reviewed_summary_count":n,"claim_count":len(claims),
      "supported_claim_count":sum(c.get("supported") is True for r in reviewed for c in r.get("claims",[])),
      "support_adjudicated_claim_count":sum(c.get("supported") in (True,False) for c in claims),
      "supported_claim_rate":mean([c.get("supported") for c in claims]),
      "unsupported_claim_rate":mean([not c["supported"] if c.get("supported") is not None else None for c in claims]),
      "critical_omission_adjudicated_count":sum(r.get("critical_omission") in (True,False) for r in reviewed),
      "critical_fact_omission_rate":mean([r.get("critical_omission") for r in reviewed]),
      "contradiction_adjudicated_count":sum(r.get("contradiction") in (True,False) for r in reviewed),
      "contradiction_rate":mean([r.get("contradiction") for r in reviewed]),
      "evidence_adjudicated_claim_count":sum(c.get("evidence_correct") in (True,False) for c in claims),
      "evidence_reference_correctness":mean([c.get("evidence_correct") for c in claims])}

def mean(values):
    adjudicated=[v for v in values if v is not None]
    return sum(adjudicated)/len(adjudicated) if adjudicated else None
