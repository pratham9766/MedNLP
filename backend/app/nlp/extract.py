import re
from app.schemas import Analysis, EvidenceItem, PageText

LAB_HINTS = re.compile(r"\b(hemoglobin|haemoglobin|glucose|creatinine|cholesterol|platelets?|sodium|potassium|wbc|rbc|tsh|hba1c|bilirubin|alt|ast)\b", re.I)
RAD_HINTS = re.compile(r"\b(impression|findings|radiograph|ct scan|mri|ultrasound|no acute|opacity|lesion|effusion)\b", re.I)
DIS_HINTS = re.compile(r"\b(discharge|medications?|follow[- ]up|admission|diagnos(?:is|es)|allerg(?:y|ies)|presenting complaint)\b", re.I)
LAB_DOC_HINTS = re.compile(r"\b(laboratory|lab report|test results|clinical chemistry)\b", re.I)
LAB_ROW = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9 /().-]{1,45}?)\s+(?P<value>[<>≤≥]?\s*\d+(?:[.,]\d+)?|positive|negative|reactive|non-reactive)\s*(?P<unit>mmol/L|mg/dL|g/dL|g/L|mL/min(?:/1\.73\s*m2)?|U/L|IU/L|10\^?\d+/?[A-Za-zμ]+|%|[A-Za-zμ]+/L)?\s*(?P<flag>H|L|high|low|abnormal|normal)?\s*(?:\((?P<range>[^()]{2,30})\))?", re.I)

def classify_document(text: str) -> str:
    scores = {"laboratory": len(LAB_HINTS.findall(text)), "radiology": len(RAD_HINTS.findall(text)), "discharge": len(DIS_HINTS.findall(text))}
    if LAB_DOC_HINTS.search(text): scores["laboratory"] += 2
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "unknown"

def _sentences(pages):
    for page in pages:
        offset = 0
        for raw_line in page.text.splitlines(keepends=True):
            line = raw_line.strip()
            local = raw_line.find(line) if line else -1
            if line: yield page.page, line, offset + local
            offset += len(raw_line)

def process_pages(pages: list[PageText], extra_warnings: list[str] | None = None) -> Analysis:
    text="\n".join(p.text for p in pages)
    kind=classify_document(text)
    items=[]; warnings=list(extra_warnings or [])
    for page_no, line, line_start in _sentences(pages):
        if kind == "laboratory":
            for n,m in enumerate(LAB_ROW.finditer(line)):
                name=m.group("name").strip(" .:-")
                if not LAB_HINTS.search(name): continue
                val=m.group("value").strip(); unit=m.group("unit"); ref=m.group("range")
                reported_flag=m.group("flag")
                norm=val+(f" {unit}" if unit else "")
                row_w=[]
                if not unit: row_w.append("Unit not stated; value requires review.")
                if ref: norm += f" (reported reference: {ref})"
                if re.search(r"[OoIl|]", val): row_w.append("Possible OCR ambiguity; original text preserved.")
                flag=None
                bounds=re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*",ref or "")
                numeric=re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*",val)
                if bounds and numeric and unit:
                    result=float(numeric.group(1)); low=float(bounds.group(1)); high=float(bounds.group(2))
                    if low<=high: flag="low" if result<low else "high" if result>high else "within_reported_range"
                    else: row_w.append("Reported reference interval could not be validated.")
                elif ref: row_w.append("Reference interval format or units are not comparable; no range flag assigned.")
                items.append(EvidenceItem(id=f"p{page_no}-lab{len(items)}", entity_type="laboratory_result", original_text=m.group(0), normalized_value=norm, unit=unit, reference_interval=ref, lab_reported_flag=reported_flag, abnormal_flag=flag, source_page=page_no, source_text=line, span_start=line_start + m.start(), span_end=line_start + m.end(), validation_warnings=row_w))
        elif kind != "unknown":
            cues = ([("radiology_finding", RAD_HINTS)] if kind=="radiology" else
                    [("diagnosis_or_symptom", re.compile(r"\b(diagnos\w*|symptom\w*|pain|fever|history of|denies|no evidence of|possible|suspected)\b", re.I)),
                     ("medication", re.compile(r"\b(mg|mcg|tablet|capsule|daily|twice daily|once daily|medication|prescribed)\b", re.I)),
                     ("follow_up", re.compile(r"\b(follow[- ]up|review in|return if|appointment)\b", re.I))] if kind=="discharge" else
                    [])
            for label,pat in cues:
                if pat.search(line):
                    negated = bool(re.search(r"\b(no|not|denies|negative|without|absent)\b", line, re.I))
                    uncertain = bool(re.search(r"\b(possible|possibly|may|might|suspected|cannot exclude|questionable)\b", line, re.I))
                    historical = bool(re.search(r"\b(history of|historical|previously|prior|resolved)\b", line, re.I))
                    items.append(EvidenceItem(id=f"p{page_no}-item{len(items)}",entity_type=label,original_text=line,normalized_value=None,source_page=page_no,source_text=line,span_start=line_start,span_end=line_start+len(line),negated=negated,uncertain=uncertain,temporality="historical" if historical else "current"))
    if kind=="unknown": warnings.append("Document type could not be classified reliably; extracted text is available for review.")
    if not items: warnings.append("No supported structured entities were extracted. Review the source text; nothing was inferred.")
    summary=("Evidence-linked statements were extracted from the report. Each item below retains its source passage. This automated extraction may be incomplete and requires human review." if items else "No supported summary could be generated from the extracted text. Please review the source document.")
    return Analysis(document_type=kind,items=items,pages=pages,summary=summary,warnings=warnings)

def process_laboratory_report(pages, warnings=None):
    return process_pages(pages,warnings)

def process_discharge_summary(pages, warnings=None):
    return process_pages(pages,warnings)

def process_radiology_report(pages, warnings=None):
    return process_pages(pages,warnings)

def validate_extracted_data(analysis: Analysis) -> Analysis:
    # Validation warnings are attached during conservative parsing; no correction is applied.
    return analysis

def generate_grounded_summary(analysis: Analysis) -> str:
    # This template only describes extraction presence; it does not paraphrase clinical claims.
    return analysis.summary
