"""Conservative, deterministic extraction with page-relative source evidence."""
import re
from app.schemas import Analysis, EvidenceItem, PageText, SummaryEvidence, PatientOverviewSection, PatientOverviewStatement, DifferentialPossibility

LAB_HINTS = re.compile(r"\b(hemoglobin|haemoglobin|hematocrit|glucose|creatinine|cholesterol|hdl|ldl|triglycerides?|platelets?|sodium|potassium|chloride|bicarbonate|carbon dioxide|urea|bun|phosphorus|calcium|albumin|protein|wbc|rbc|mcv|mchc?|rdw|tsh|hba1c|a1c|bilirubin|alt|ast|ferritin|iron|transferrin|reticulocyte|folate|vitamin b12|egfr|estimated gfr|urine albumin|specific gravity|nitrite|leukocyte esterase)\b", re.I)
RAD_HINTS = re.compile(r"\b(impression|findings|recommendations?|radiograph|ct scan|computed tomography|mri|ultrasound|no acute|opacity|lesion|effusion|infarct|hemorrhage|consolidation|pneumothorax|fracture|nodule|atelectasis|edema|lymph node)\b", re.I)
DIS_HINTS = re.compile(r"\b(discharge|medications?|follow[- ]up|admission|diagnos(?:is|es)|allerg(?:y|ies)|presenting complaint|history of)\b", re.I)
LAB_DOC_HINTS = re.compile(r"\b(laboratory|lab(?:oratory)? results?|test results|clinical chemistry)\b", re.I)
NUMERIC_TOKEN = r"[0-9OoIl|]+(?:[.,][0-9OoIl|]+)?"
LAB_UNIT = r"mmol/L|mg/dL|g/dL|g/L|mL/min(?:/1\.73\s*m2)?|U/L|IU/L|10\^?\d+/?[A-Za-zμ]+|%|[A-Za-zμ]+/L"
LAB_VALUE = r"[<>≤≥]?\s*(?:"+NUMERIC_TOKEN+r"|non-reactive|nonreactive|positive|negative|reactive)"
LAB_RANGE = r"(?:<\s*"+NUMERIC_TOKEN+r"|"+NUMERIC_TOKEN+r"\s*[-–]\s*"+NUMERIC_TOKEN+r")(?:\s+(?:"+LAB_UNIT+r"))?"
LAB_ROW = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9 ,/().-]{1,60}?)\s+(?P<value>"+LAB_VALUE+r")\s*(?P<unit>"+LAB_UNIT+r")?\s*(?P<flag>H|L|high|low|abnormal|normal)?\s*(?:\((?P<range>[^()]{2,40})\))?", re.I)
LAB_TABLE_ROW = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9 ,/().-]{1,60}?)\s{2,}(?P<value>"+LAB_VALUE+r")\s{2,}(?P<unit>"+LAB_UNIT+r")?\s{2,}(?P<range>"+LAB_RANGE+r")(?:\s{2,}(?P<flag>H|L|high|low|abnormal|normal))?", re.I)
NUMBER = r"\d+(?:[.,]\d+)?"

def classify_with_evidence(text: str) -> tuple[str, dict[str, int]]:
    scores = {"laboratory": len(LAB_HINTS.findall(text)), "radiology": len(RAD_HINTS.findall(text)), "discharge": len(DIS_HINTS.findall(text))}
    if LAB_DOC_HINTS.search(text): scores["laboratory"] += 2
    title="\n".join(text.splitlines()[:6])
    if re.search(r"\b(?:hospital )?discharge summary\b|\bworkup summary\b|\bdifferential assessment\b",title,re.I): scores["discharge"]+=25
    if re.search(r"\b(?:radiology report|computed tomography|magnetic resonance imaging|ultrasound examination)\b",title,re.I): scores["radiology"]+=25
    if re.search(r"\b(?:laboratory results?|clinical chemistry|complete blood count)\b",title,re.I): scores["laboratory"]+=25
    best = max(scores.values(), default=0)
    winners = [name for name, score in scores.items() if score == best and score > 0]
    # A tie across document types is ambiguous; do not force an arbitrary class.
    kind = winners[0] if best >= 2 and len(winners) == 1 else "unknown"
    return kind, scores

def classify_document(text: str) -> str:
    return classify_with_evidence(text)[0]

def _sentences(pages):
    for page in pages:
        offset = 0
        for raw_line in page.text.splitlines(keepends=True):
            line = raw_line.strip()
            local = raw_line.find(line) if line else -1
            if line:
                base=offset+local; start=0
                boundaries=[]
                if not re.match(r"\s*(?:status in note|evidence recorded in (?:support|as limiting))\s*:",line,re.I):
                    boundaries=list(re.finditer(r"(?<=;)\s+|(?<!\d)(?<=[.!?])\s+(?=[A-Z])",line))
                    if re.match(r"\s*\d+[.)]\s+", line):
                        boundaries=[boundary for boundary in boundaries if not re.match(r"\s*\d+[.)]$", line[:boundary.start()])]
                for boundary in boundaries:
                    previous=line[max(start,boundary.start()-8):boundary.start()].casefold().rstrip()
                    if re.search(r"\b(?:dr|mr|mrs|ms|prof|fig|e\.g|i\.e)\.$",previous): continue
                    statement=line[start:boundary.start()].strip()
                    if statement:
                        position=line.find(statement,start)
                        yield page.page,statement,base+position
                    start=boundary.end()
                statement=line[start:].strip()
                if statement:
                    position=line.find(statement,start)
                    yield page.page,statement,base+position
            offset += len(raw_line)


def _negated(text):
    lowered=text.casefold()
    if re.search(r"\b(?:not|cannot|can not)\s+(?:be\s+)?ruled out\b|\bcannot exclude\b|\bnot excluded\b",lowered): return False
    return bool(re.search(r"\b(?:no|without|absent|negative for|denies|denied|not seen|not identified|not present|not observed|not demonstrated|not detected|not reported|not documented|ruled out|free of)\b",lowered))


def _uncertain(text):
    return bool(re.search(r"\b(?:possible|possibly|may|might|suspected|cannot exclude|questionable|suggestive of|could be|could represent|less likely|not ruled out|uncertain|considered)\b",text,re.I))


def _temporality(text,entity_type=None):
    historical=bool(re.search(r"\b(?:history of|remote history|historical|previously (?:diagnosed|reported|documented|seen)|prior (?:diagnosis|history)|resolved|old (?:infarct|lesion|fracture|opacity|nodule))\b",text,re.I))
    comparison_current=bool(re.search(r"\b(?:is|are|remains|remain) unchanged since (?:the )?(?:prior|previous)\b",text,re.I))
    if comparison_current: historical=False
    current=bool(re.search(r"\b(?:current(?:ly)?|today|now|this (?:study|examination|visit|stay)|on admission|at admission|during this stay|present at|acute)\b",text,re.I))
    if historical and current: return "unknown"
    if historical: return "historical"
    if entity_type and entity_type.startswith("differential_") and not current: return "unknown"
    return "current"


MEDICATION_NAMES=re.compile(r"\b(amoxicillin|azithromycin|acetaminophen|paracetamol|ibuprofen|furosemide|frusemide|carvedilol|empagliflozin|aspirin|albuterol|metformin|insulin|potassium supplement|warfarin|apixaban|rivaroxaban|lisinopril|losartan|prednisone|atorvastatin|omeprazole|levothyroxine|metoprolol|amlodipine|spironolactone|dapagliflozin|clopidogrel|inhaled corticosteroid)\b",re.I)
DOSE_PATTERN=re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|μg|g|mL|units?)\b",re.I)
ROUTE_PATTERN=re.compile(r"\b(by mouth|oral(?:ly)?|PO|intravenous|IV|intramuscular|IM|subcutaneous|inhaled|by inhalation|topical|transdermal)\b",re.I)
FREQUENCY_PATTERN=re.compile(r"\b(once daily|twice daily|three times daily|four times daily|once a day|twice a day|three times a day|daily|every\s+\d+(?:[-–]\d+)?\s+hours?|q\d+h|as needed|PRN|weekly)\b",re.I)
DURATION_PATTERN=re.compile(r"\b(for\s+(?:\d+\s+)?(?:more\s+)?(?:days?|weeks?|months?)|through\s+\d{4}-\d{2}-\d{2}|until\s+\d{4}-\d{2}-\d{2})\b",re.I)


def _medication_details(line):
    names=list(MEDICATION_NAMES.finditer(line)); doses=list(DOSE_PATTERN.finditer(line))
    medication_name=names[0].group(0) if len(names)==1 else None
    dose=doses[0].group(0) if len(doses)==1 else None
    route_match=ROUTE_PATTERN.search(line); frequency_match=FREQUENCY_PATTERN.search(line); duration_match=DURATION_PATTERN.search(line)
    change=None
    if re.search(r"\b(?:increased|raised|up[- ]titrated)\b",line,re.I): change="dose_increased"
    elif re.search(r"\b(?:decreased|reduced|lowered|down[- ]titrated)\b",line,re.I): change="dose_decreased"
    elif re.search(r"\b(?:discontinued|stopped)\b",line,re.I): change="stopped"
    elif re.search(r"\b(?:held|withheld)\b",line,re.I): change="held"
    elif re.search(r"\b(?:resumed|restarted)\b",line,re.I): change="resumed"
    elif re.search(r"\b(?:started|initiated|began|prescribed)\b",line,re.I): change="started"
    elif re.search(r"\b(?:continued|unchanged)\b",line,re.I): change="continued"
    elif re.search(r"\b(?:changed|adjusted)\b",line,re.I): change="dose_changed"
    action=bool(change or doses or re.search(r"\bmedications?\s*:",line,re.I))
    return {"medication_name":medication_name,"dose":dose,"route":route_match.group(1) if route_match else None,"frequency":frequency_match.group(1) if frequency_match else None,"duration":duration_match.group(1) if duration_match else None,"medication_change":change,"action":action,"name_count":len(names),"dose_count":len(doses)}

def _numeric_result(value: str):
    match = re.fullmatch(r"\s*(?P<cmp>[<>≤≥])?\s*(?P<num>"+NUMBER+r")\s*", value)
    if not match: return None, None, None
    raw = match.group("num")
    # A comma followed by three digits is ambiguous (decimal vs thousands separator).
    if "," in raw and len(raw.rsplit(",",1)[-1]) == 3: return None, match.group("cmp"), "Numeric value uses an ambiguous comma separator."
    try: parsed = float(raw.replace(",", "."))
    except ValueError: return None, match.group("cmp"), "Numeric value could not be parsed."
    return parsed, match.group("cmp"), None

def _reported_range(raw: str | None):
    if not raw: return None
    return re.fullmatch(r"\s*(?P<low>"+NUMBER+r")\s*[-–]\s*(?P<high>"+NUMBER+r")(?:\s+(?P<unit>[^\s()]+))?\s*", raw)

def _compare_lab_result(numeric, comparator, unit, reference, qualitative, prior_warning=None):
    unavailable = {"comparison_status": "comparison_unavailable", "reference_low": None, "reference_high": None, "abnormal_flag": None}
    if prior_warning:
        return {**unavailable, "comparison_note": prior_warning, "warning": prior_warning}
    if qualitative:
        note = "Qualitative results are not compared numerically."
        return {**unavailable, "comparison_note": note, "warning": note}
    if not reference:
        note = "No laboratory-provided reference interval is available."
        return {**unavailable, "comparison_note": note, "warning": note}
    if comparator:
        note = "Inequalities are preserved; numeric interval comparison is unavailable."
        return {**unavailable, "comparison_note": note, "warning": note}
    if numeric is None:
        note = "Result is not a parseable numeric value."
        return {**unavailable, "comparison_note": note, "warning": note}
    if not unit:
        note = "Result unit is missing; comparison is unavailable."
        return {**unavailable, "comparison_note": note, "warning": note}
    interval = _reported_range(reference)
    if not interval:
        note = "Reported reference interval could not be parsed."
        return {**unavailable, "comparison_note": note, "warning": note}
    range_unit = interval.group("unit")
    if range_unit and range_unit.casefold() != unit.casefold():
        note = "Reference interval unit is incompatible with the result unit."
        return {**unavailable, "comparison_note": note, "warning": note}
    low_raw, high_raw = interval.group("low"), interval.group("high")
    if any("," in raw and len(raw.rsplit(",", 1)[-1]) == 3 for raw in (low_raw, high_raw)):
        note = "Reference interval contains an ambiguous comma separator."
        return {**unavailable, "comparison_note": note, "warning": note}
    try:
        low, high = float(low_raw.replace(",", ".")), float(high_raw.replace(",", "."))
    except ValueError:
        note = "Reference interval bounds could not be normalized."
        return {**unavailable, "comparison_note": note, "warning": note}
    if low >= high:
        note = "Reference interval bounds are invalid or have zero width."
        return {**unavailable, "comparison_note": note, "warning": note}
    status = "below_reported_range" if numeric < low else "above_reported_range" if numeric > high else "within_reported_range"
    return {"comparison_status": status, "reference_low": low, "reference_high": high,
            "abnormal_flag": {"below_reported_range": "low", "above_reported_range": "high"}.get(status, "within_reported_range"),
            "comparison_note": None, "warning": None}

def _radiology_context(text: str):
    modality_match = re.search(r"\b(CT|MRI|MR|X[- ]?ray|radiograph|ultrasound|US)\b", text, re.I)
    region_match = re.search(r"\b(chest|brain|head|abdomen|pelvis|spine|knee|neck|thorax)\b", text, re.I)
    return (modality_match.group(1).upper() if modality_match else None, region_match.group(1).lower() if region_match else None)

def _patient_overview(items: list[EvidenceItem]) -> list[PatientOverviewSection]:
    """Group source-backed statements without introducing clinical interpretation."""
    titles={"findings":"Reported findings","possibilities":"Possibilities mentioned in the report",
            "negative_findings":"Negative findings documented in the report","history":"Relevant history",
            "medications":"Medications and care","recommendations":"Recommendations and follow-up",
            "clarifications":"Items needing clarification"}
    groups={key:[] for key in titles}
    seen={}
    for item in items:
        if item.source_page is None or not item.original_text:
            continue
        if item.entity_type=="laboratory_result":
            key="findings"
            text=f"{item.analyte or 'Test'}: {item.normalized_value or item.original_text}"
            if item.comparison_status=="above_reported_range": explanation="Higher than the interval printed by this laboratory."
            elif item.comparison_status=="below_reported_range": explanation="Lower than the interval printed by this laboratory."
            elif item.comparison_status=="within_reported_range": explanation="Within the interval printed by this laboratory; this comparison alone does not determine what is healthy for you."
            else: explanation=None
        elif item.entity_type in {"differential_possibility","differential_evidence_for","differential_evidence_against","differential_status"} or (item.uncertain and item.entity_type in {"diagnosis_or_symptom","radiology_finding","radiology_impression"}):
            key="possibilities"
            text=("Evidence recorded in support: " if item.entity_type=="differential_evidence_for" else "Evidence recorded as limiting: " if item.entity_type=="differential_evidence_against" else "")+item.original_text
            explanation="The report presents this as uncertain, not as a confirmed diagnosis." if item.entity_type in {"differential_possibility","differential_status"} or item.uncertain else None
        elif item.temporality=="historical": key="history"; text=item.original_text; explanation=None
        elif item.entity_type=="allergy": key="history"; text=item.original_text; explanation=None
        elif item.entity_type=="medication": key="medications"; text=item.original_text; explanation=None
        elif item.entity_type in {"follow_up","radiology_recommendation"}: key="recommendations"; text=item.original_text; explanation="The report documents this as a recommendation; it does not confirm that the action was completed."
        elif item.negated: key="negative_findings"; text=item.original_text; explanation="This is a specific negative statement in the report; it does not rule out findings the report did not assess."
        elif item.validation_warnings or not item.source_text: key="clarifications"; text=item.original_text; explanation="This extracted information needs checking against the original report."
        else: key="findings"; text=item.original_text; explanation=None
        identity=(key,item.source_page,item.original_text)
        if identity in seen:
            existing=seen[identity]
            if item.id not in existing.source_evidence_ids: existing.source_evidence_ids.append(item.id)
            continue
        statement=PatientOverviewStatement(text=text,source_evidence_ids=[item.id],source_page=item.source_page,original_text=item.original_text,explanation=explanation)
        groups[key].append(statement); seen[identity]=statement
    return [PatientOverviewSection(key=key,title=titles[key],statements=statements) for key,statements in groups.items() if statements]

def process_pages(pages: list[PageText], extra_warnings: list[str] | None = None) -> Analysis:
    text = "\n".join(p.text for p in pages)
    kind, classification_evidence = classify_with_evidence(text)
    items=[]; warnings=list(extra_warnings or [])
    modality, body_region = _radiology_context(text)
    section = "other"
    in_differential=False
    differential_possibilities=[]
    active_possibility=None
    for page_no, line, line_start in _sentences(pages):
        if re.search(r"\bdifferential(?: diagnosis)?(?: assessment| workup)?\b",line,re.I): in_differential=True
        if re.search(r"\b(?:documented plan|end of report|end of fictional|discharge medications|follow[- ]?up|medication reconciliation)\b",line,re.I):
            in_differential=False; active_possibility=None
        section_match = re.match(r"\s*(findings|impression|recommendations?)\s*:?\s*", line, re.I)
        if section_match:
            word = section_match.group(1).lower()
            section = "recommendations" if word.startswith("recommend") else word
        if kind == "laboratory":
            table_matches=list(LAB_TABLE_ROW.finditer(line))
            matches=table_matches or list(LAB_ROW.finditer(line))
            for match in matches:
                name=match.group("name").strip(" .:-")
                if not LAB_HINTS.search(name): continue
                value=match.group("value").strip(); unit=match.group("unit"); ref=match.group("range"); reported_flag=match.group("flag")
                ocr_ambiguous=bool(re.fullmatch(r"\s*[<>≤≥]?\s*"+NUMERIC_TOKEN+r"\s*",value) and re.search(r"[OoIl|]",value))
                normalized=value+(f" {unit}" if unit else "")
                row_w=[]
                if not unit: row_w.append("Unit not stated; value requires review.")
                if ref: normalized += f" (reported reference: {ref})"
                if ocr_ambiguous:
                    row_w.append("Possible OCR ambiguity; original text preserved and numeric normalization withheld.")
                    normalized=None
                numeric, comparator, numeric_warning = _numeric_result(value)
                if numeric_warning: row_w.append(numeric_warning)
                qualitative=value.lower() if value.lower() in {"positive","negative","reactive","non-reactive"} else None
                comparison=_compare_lab_result(numeric, comparator, unit, ref, qualitative, "Possible OCR ambiguity; numeric comparison withheld." if ocr_ambiguous else numeric_warning)
                if comparison["warning"] and comparison["warning"] not in row_w: row_w.append(comparison["warning"])
                items.append(EvidenceItem(id=f"p{page_no}-lab{len(items)}",entity_type="laboratory_result",original_text=match.group(0),analyte=name,numeric_value=numeric,comparator=comparator,qualitative_value=qualitative,normalized_value=normalized,unit=unit,reference_interval=ref,lab_reported_flag=reported_flag,source_page=page_no,source_text=line,span_start=line_start+match.start(),span_end=line_start+match.end(),extraction_method="deterministic-lab-rules-v3",validation_warnings=row_w,**{k:v for k,v in comparison.items() if k!="warning"}))
        elif kind == "radiology":
            heading_only=(line.isupper() and len(line)<100 and not re.search(r"[.!?]",line)) or (bool(re.fullmatch(r"(?:CT|MRI|MR|X[- ]?ray|radiograph|ultrasound|US)\s+(?:of\s+)?[A-Za-z -]+",line,re.I)) and not re.search(r"\b(findings|impression|no acute|opacity|lesion|effusion|infarct|hemorrhage)\b",line,re.I))
            section_text=line[section_match.end():].strip() if section_match else line
            if not section_text or heading_only or (not RAD_HINTS.search(section_text) and not section_match): continue
            quote=line
            entity_type="radiology_impression" if section=="impression" else "radiology_recommendation" if section=="recommendations" else "radiology_finding"
            items.append(EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type=entity_type,original_text=quote,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start,span_end=line_start+len(line),negated=_negated(line),uncertain=_uncertain(line),temporality=_temporality(line,entity_type),modality=modality,body_region=body_region,report_section=section,extraction_method="deterministic-radiology-rules-v3"))
        elif kind == "discharge":
            if line.isupper() and len(line)<100 and not re.search(r"[.!?]",line):
                continue
            if in_differential:
                candidate_list=re.match(r"\s*(?:differential(?: diagnoses?)?|possibilities)\s*(?:include|includes|:)\s*:?[ \t]*(?P<list>.+?)\s*$",line,re.I)
                if candidate_list:
                    tail=candidate_list.group("list")
                    cursor=line.find(tail)
                    for raw_candidate in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+",tail,flags=re.I):
                        name=raw_candidate.strip().rstrip(".;:")
                        if len(name)<3: continue
                        start=line.find(name,cursor); cursor=start+len(name)
                        lowered=name.casefold()
                        status="ruled_out" if "ruled out" in lowered and "not ruled out" not in lowered else "less_likely" if "less likely" in lowered else "favored" if "favored" in lowered else "suspected" if "suspected" in lowered else "likely" if re.search(r"\blikely\b",lowered) else "possible" if any(cue in lowered for cue in ("possible","cannot exclude","not excluded")) else "considered"
                        item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type="differential_possibility",original_text=name,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start+start,span_end=line_start+start+len(name),uncertain=True,extraction_method="deterministic-differential-rules-v1")
                        items.append(item); differential_possibilities.append({"text":name,"item":item,"source":[item.id],"for":[],"against":[],"status":status,"uncertainty":name if status!="considered" else None})
                    continue
                candidate=re.match(r"\s*\d+[.)]\s+(?P<name>.+?)\s*$",line)
                if candidate:
                    name=candidate.group("name").rstrip(".;:")
                    start=line.find(name,candidate.start("name"))
                    item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type="differential_possibility",original_text=name,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start+start,span_end=line_start+start+len(name),uncertain=True,temporality="unknown",extraction_method="deterministic-differential-rules-v2")
                    items.append(item); active_possibility={"text":candidate.group("name"),"item":item,"source":[item.id],"for":[],"against":[],"status":"uncertain","uncertainty":None}; differential_possibilities.append(active_possibility)
                    continue
                if active_possibility:
                    support=bool(re.search(r"\bEvidence recorded in support\s*:",line,re.I))
                    limiting=bool(re.search(r"\bEvidence recorded as limiting\s*:",line,re.I))
                    status_match=re.search(r"\bStatus in note\s*:\s*(.*)",line,re.I)
                    if support or limiting:
                        cue="Evidence recorded in support:" if support else "Evidence recorded as limiting:"
                        excerpt=line[line.lower().find(cue.lower()):]
                        source_item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type="differential_evidence_for" if support else "differential_evidence_against",original_text=excerpt,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start+line.find(excerpt),span_end=line_start+line.find(excerpt)+len(excerpt),negated=_negated(excerpt),uncertain=_uncertain(excerpt),temporality="unknown",extraction_method="deterministic-differential-rules-v2")
                        items.append(source_item); (active_possibility["for"] if support else active_possibility["against"]).append(source_item.id)
                    if status_match:
                        wording=status_match.group(1).strip()
                        active_possibility["uncertainty"]=wording
                        status_text=line[line.lower().find("status in note:"):]
                        status_item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type="differential_status",original_text=status_text,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start+line.find(status_text),span_end=line_start+line.find(status_text)+len(status_text),negated=_negated(status_text),uncertain=True,temporality="unknown",extraction_method="deterministic-differential-rules-v2")
                        items.append(status_item); active_possibility["source"].append(status_item.id)
                        lowered=wording.casefold()
                        if re.search(r"\b(?:not|cannot|can not)\s+(?:be\s+)?ruled out\b|\bcannot exclude\b|\bnot excluded\b",lowered): active_possibility["status"]="possible"
                        elif "ruled out" in lowered and any(cue in lowered for cue in ("possible","likely","cannot","not excluded")): active_possibility["status"]="uncertain"
                        elif "ruled out" in lowered: active_possibility["status"]="ruled_out"
                        elif "less likely" in lowered or "less supported" in lowered: active_possibility["status"]="less_likely"
                        elif "favored" in lowered: active_possibility["status"]="favored"
                        elif "suspected" in lowered: active_possibility["status"]="suspected"
                        elif "considered" in lowered: active_possibility["status"]="considered"
                        elif re.search(r"\blikely\b",lowered): active_possibility["status"]="likely"
                        elif "possible" in lowered or "cannot exclude" in lowered or "not excluded" in lowered: active_possibility["status"]="possible"
                    if support or limiting or status_match: continue
            cues=[("allergy",re.compile(r"\ballerg\w*\b",re.I)),("diagnosis_or_symptom",re.compile(r"\b(diagnos\w*|symptom\w*|pain|fever|cough|history of|denies|no evidence of|possible|suspected|exacerbation|hypotension|confusion|dyspnea|shortness of breath|edema|swelling|nausea|vomiting|weakness|palpitations|rash|seizure|stroke|infection)\b|\b(?:no|without|absent|negative for)\s+(?:current\s+)?(?:fever|cough|pain|hypotension|confusion|exacerbation|dyspnea|shortness of breath|edema|swelling|nausea|vomiting|weakness|palpitations|rash|seizure|stroke|infection)\b",re.I)),("medication",re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|mL|units?)\b|"+MEDICATION_NAMES.pattern+r"|^\s*medications?\s*:",re.I)),("follow_up",re.compile(r"\b(follow[- ]up|review in|return if|appointment)\b",re.I))]
            for label,pattern in cues:
                if not pattern.search(line): continue
                if label=="medication":
                    details=_medication_details(line)
                    if not details["action"]: continue
                    item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type=label,original_text=line,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start,span_end=line_start+len(line),negated=_negated(line),uncertain=_uncertain(line),temporality=_temporality(line,label),extraction_method="deterministic-medication-rules-v2",**{key:details[key] for key in ("medication_name","dose","route","frequency","duration","medication_change")})
                    if details["name_count"]!=1: item.validation_warnings.append("Medication name is missing or ambiguous; source statement preserved for review.")
                    if details["dose_count"]>1: item.validation_warnings.append("Multiple dose values occur in this source statement; dose normalization withheld.")
                    items.append(item)
                    continue
                item=EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type=label,original_text=line,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start,span_end=line_start+len(line),negated=_negated(line),uncertain=_uncertain(line),temporality=_temporality(line,label),extraction_method="deterministic-discharge-rules-v3")
                items.append(item)
    if kind=="unknown": warnings.append("Document type could not be classified reliably or multiple types were tied; extracted text is available for review.")
    overview=_patient_overview(items)
    possibilities=[DifferentialPossibility(possibility_text=entry["text"],assertion_status=entry["status"],evidence_for=entry["for"],evidence_against=entry["against"],uncertainty_text=entry["uncertainty"],source_evidence_ids=entry["source"]) for entry in differential_possibilities]
    if not items:
        warnings.append("No supported structured entities were extracted. Review the source text; nothing was inferred.")
        summary="No structured statements were extracted. The source text is available for review."
    elif kind=="laboratory":
        outside=sum(item.comparison_status in {"above_reported_range","below_reported_range"} for item in items if item.entity_type=="laboratory_result")
        unavailable=sum(item.comparison_status=="comparison_unavailable" for item in items if item.entity_type=="laboratory_result")
        summary=f"{sum(item.entity_type=='laboratory_result' for item in items)} laboratory results were extracted. {outside} compare outside a range printed by the laboratory; {unavailable} could not be compared reliably. These comparisons are not diagnoses."
    else:
        summary=f"{len(overview)} patient-friendly sections organize {len(items)} extracted source items. Possible findings, negative statements, history, and follow-up remain tied to the report wording and should be checked against the source."
    summary_evidence=[]; seen_summary=set()
    for item in items:
        identity=(item.source_page,item.span_start,item.span_end,item.original_text)
        if item.source_page is None or item.span_start is None or item.span_end is None or identity in seen_summary: continue
        seen_summary.add(identity)
        summary_evidence.append(SummaryEvidence(statement=item.original_text,source_page=item.source_page,quote=item.original_text,span_start=item.span_start,span_end=item.span_end))
    return Analysis(document_type=kind,items=items,pages=pages,summary=summary,warnings=warnings,classification_evidence=classification_evidence,summary_evidence=summary_evidence,patient_overview=overview,differential_possibilities=possibilities)

def process_laboratory_report(pages,warnings=None): return process_pages(pages,warnings)
def process_discharge_summary(pages,warnings=None): return process_pages(pages,warnings)
def process_radiology_report(pages,warnings=None): return process_pages(pages,warnings)
def validate_extracted_data(analysis:Analysis)->Analysis: return analysis
def generate_grounded_summary(analysis:Analysis)->str: return analysis.summary
