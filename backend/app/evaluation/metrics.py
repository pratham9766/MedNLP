"""Transparent exact-span and clinical-attribute metrics."""
from collections import defaultdict

def score_entities(gold, predicted):
    key = lambda x: (x["source_page"], x["start_char"], x["end_char"], x["entity_type"])
    g = {key(x): x for x in gold}; p = {key(x): x for x in predicted}
    tp = len(g.keys() & p.keys()); fp = len(p.keys() - g.keys()); fn = len(g.keys() - p.keys())
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    per_type = {}
    for typ in sorted({x["entity_type"] for x in gold+predicted}):
        gt=[x for x in gold if x["entity_type"]==typ]; pt=[x for x in predicted if x["entity_type"]==typ]
        kt=lambda x:(x["source_page"],x["start_char"],x["end_char"],x["entity_type"])
        t=len({kt(x) for x in gt}&{kt(x) for x in pt}); fpos=len({kt(x) for x in pt}-{kt(x) for x in gt}); fneg=len({kt(x) for x in gt}-{kt(x) for x in pt})
        pr=t/(t+fpos) if t+fpos else 0.0; re=t/(t+fneg) if t+fneg else 0.0
        per_type[typ]={"true_positive":t,"false_positive":fpos,"false_negative":fneg,"precision":pr,"recall":re,"strict_span_f1":2*pr*re/(pr+re) if pr+re else 0.0}
    matches = [(g[k],p[k]) for k in g.keys() & p.keys()]
    lab = [(a,b) for a,b in matches if a["entity_type"]=="laboratory_result"]
    def accuracy(field):
        eligible=[(a,b) for a,b in lab if a.get(field) is not None]
        return {"correct":sum(a.get(field)==b.get(field) for a,b in eligible),"count":len(eligible),"accuracy":sum(a.get(field)==b.get(field) for a,b in eligible)/len(eligible) if eligible else None}
    attrs = {}
    for field in ("negation","uncertainty"):
        eligible=[(a,b) for a,b in matches]
        attrs[field+"_error_rate"]={"errors":sum(bool(a.get(field))!=bool(b.get(field)) for a,b in eligible),"count":len(eligible),"rate":sum(bool(a.get(field))!=bool(b.get(field)) for a,b in eligible)/len(eligible) if eligible else None}
    return {"true_positive":tp,"false_positive":fp,"false_negative":fn,"precision":precision,"recall":recall,"strict_span_f1":f1,"per_entity":per_type,"lab_value_exact_match":accuracy("normalized_value"),"unit_accuracy":accuracy("unit"),"reference_interval_accuracy":accuracy("reference_interval"),**attrs}

def summarize_review(records):
    """Records are manually adjudicated claims; only reviewed records enter denominators."""
    reviewed=[r for r in records if r.get("reviewed") is True]
    n=len(reviewed)
    return {"reviewed_summary_count":n,"claim_count":sum(len(r.get("claims",[])) for r in reviewed),
      "supported_claim_count":sum(c.get("supported") is True for r in reviewed for c in r.get("claims",[])),
      "support_adjudicated_claim_count":sum(c.get("supported") in (True,False) for r in reviewed for c in r.get("claims",[])),
      "supported_claim_rate":mean([c.get("supported") for r in reviewed for c in r.get("claims",[])]),
      "unsupported_claim_rate":mean([not c["supported"] if c.get("supported") is not None else None for r in reviewed for c in r.get("claims",[])]),
      "critical_fact_omission_rate":mean([r.get("critical_omission") for r in reviewed]),
      "contradiction_rate":mean([r.get("contradiction") for r in reviewed]),
      "evidence_reference_correctness":mean([c.get("evidence_correct") for r in reviewed for c in r.get("claims",[])])}

def mean(values):
    adjudicated=[v for v in values if v is not None]
    return sum(adjudicated)/len(adjudicated) if adjudicated else None
