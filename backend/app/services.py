import io
from pathlib import Path
from PIL import Image
from app.schemas import PageText

def extract_document_text(path: Path, mime: str):
    pages=[]; warnings=[]
    if mime=="application/pdf":
        import fitz
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
    terms={w.lower() for w in question.split() if len(w)>2}
    ranked=[]
    for p in pages:
        for line in p.get("text", "").splitlines():
            score=sum(line.lower().count(t) for t in terms)
            if score: ranked.append((score,p["page"],line.strip()))
    ranked.sort(reverse=True)
    evidence=[{"page":p,"quote":line} for _,p,line in ranked[:4]]
    return {"answer":("The report contains these potentially relevant passages. This prototype retrieves evidence but does not infer beyond the quoted text." if evidence else "The report does not contain enough matching evidence to answer this question."),"evidence":evidence,"method":"lexical retrieval; extractive response"}
