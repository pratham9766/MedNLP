import io
import re
from pathlib import Path
from PIL import Image
from app.schemas import PageText

def extract_document_text(path: Path, mime: str):
    pages=[]; warnings=[]
    if mime=="application/pdf":
        import pymupdf as fitz
        doc=fitz.open(path)
        if len(doc)>100: raise ValueError("page_limit")
        for i,p in enumerate(doc):
            text=p.get_text("text").strip()
            if text: pages.append(PageText(page=i+1,text=text,extraction_method="pymupdf"))
            else:
                try:
                    import pytesseract
                    pix=p.get_pixmap(matrix=fitz.Matrix(2,2)); image=Image.open(io.BytesIO(pix.tobytes("png")))
                    pages.append(PageText(page=i+1,text=pytesseract.image_to_string(image).strip(),extraction_method="tesseract-ocr"))
                except Exception:
                    pages.append(PageText(page=i+1,text="",extraction_method="unavailable")); warnings.append(f"Page {i+1} has no embedded text; OCR unavailable or failed.")
        return pages,len(doc),warnings
    try:
        import pytesseract
        pages=[PageText(page=1,text=pytesseract.image_to_string(Image.open(path)).strip(),extraction_method="tesseract-ocr")]
    except Exception:
        pages=[PageText(page=1,text="",extraction_method="unavailable")]; warnings.append("Image OCR unavailable or failed. Install Tesseract and pytesseract to process this image.")
    return pages,1,warnings

def answer_report_question(question: str, pages: list[dict]):
    # A transparent lexical retriever; never calls a model or uses another report.
    stopwords={"what","which","when","where","who","does","did","was","were","has","have","had","the","this","that","about","report","result","show","tell","me","any","are","is","of","in","on","for","patient"}
    terms={w.lower().strip(".,?!:;()[]{}") for w in question.split() if len(w)>2 and w.lower().strip(".,?!:;()[]{}") not in stopwords}
    ranked=[]
    for p in pages:
        offset=0
        for raw in p.get("text", "").splitlines(keepends=True):
            line=raw.strip(); local=raw.find(line) if line else -1
            score=sum(line.lower().count(t) for t in terms)
            if score: ranked.append((score,p["page"],line,offset+local,offset+local+len(line)))
            offset+=len(raw)
    ranked.sort(key=lambda x:(-x[0],x[1],x[3]))
    evidence=[{"page":p,"quote":line,"start_char":start,"end_char":end,"kind":"source_passage"} for _,p,line,start,end in ranked[:4]]
    conflict=False
    if len(evidence)>1:
        states=[]
        for item in evidence:
            q=item["quote"].lower()
            states.append(bool(re.search(r"\b(no|not|denies|negative|without|absent)\b",q)))
        conflict=any(x!=states[0] for x in states[1:]) and len({w for w in terms if any(w in e["quote"].lower() for e in evidence)})>0
    answer=("The matching report passages contain differing polarity or uncertainty cues. Review both passages; no conclusion is inferred." if conflict else "The report contains these potentially relevant source passages. This extractive prototype does not infer beyond the quoted text." if evidence else "The report does not contain enough matching evidence to answer this question.")
    return {"answer":answer,"evidence":evidence,"method":"lexical retrieval; extractive response","answer_type":"source_passages" if evidence else "insufficient_evidence"}
