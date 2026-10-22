import io
import re
from pathlib import Path
from PIL import Image
from app.schemas import PageText
from app.core.config import settings

class UploadValidationError(ValueError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail); self.status_code=status_code; self.detail=detail

def _configure_tesseract(pytesseract):
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd=settings.tesseract_cmd

def validate_upload_content(data: bytes, mime: str, max_bytes: int, max_pages: int) -> int | None:
    if mime not in {"application/pdf","image/png","image/jpeg"}: raise UploadValidationError(415,"Supported formats are PDF, PNG, and JPEG.")
    if not data: raise UploadValidationError(400,"The uploaded file is empty.")
    if len(data)>max_bytes: raise UploadValidationError(413,"File exceeds the configured upload size limit.")
    if mime=="application/pdf":
        if not data.startswith(b"%PDF-"): raise UploadValidationError(400,"The file signature does not match a PDF.")
        try:
            import pymupdf as fitz
            with fitz.open(stream=data,filetype="pdf") as doc:
                if doc.needs_pass: raise UploadValidationError(400,"Password-protected PDFs are not supported.")
                if not len(doc): raise UploadValidationError(400,"The PDF contains no pages.")
                if len(doc)>max_pages: raise UploadValidationError(413,f"PDF exceeds the {max_pages}-page limit.")
                return len(doc)
        except UploadValidationError: raise
        except Exception as exc: raise UploadValidationError(400,"The PDF is malformed or unreadable.") from exc
    signature=b"\x89PNG\r\n\x1a\n" if mime=="image/png" else b"\xff\xd8\xff"
    if not data.startswith(signature): raise UploadValidationError(400,"The file signature does not match the selected image type.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            expected="PNG" if mime=="image/png" else "JPEG"
            if image.format!=expected: raise UploadValidationError(400,"The image content does not match the declared image type.")
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>40_000_000: raise UploadValidationError(413,"Image dimensions exceed the supported pixel limit.")
    except UploadValidationError: raise
    except Exception as exc: raise UploadValidationError(400,"The image is malformed or unreadable.") from exc
    return 1

def extract_document_text(path: Path, mime: str, max_pages: int = 100):
    pages=[]; warnings=[]
    if mime=="application/pdf":
        import pymupdf as fitz
        with fitz.open(path) as doc:
            if doc.needs_pass: raise ValueError("encrypted_pdf")
            if len(doc)>max_pages: raise ValueError("page_limit")
            count=len(doc)
            for i,p in enumerate(doc):
                text=p.get_text("text").strip()
                has_images=bool(p.get_images(full=True))
                sparse=len(text)<80
                if text and not (has_images and sparse):
                    pages.append(PageText(page=i+1,text=text,extraction_method="pymupdf"))
                    continue
                if not has_images and text:
                    pages.append(PageText(page=i+1,text=text,extraction_method="pymupdf"))
                    warnings.append(f"Page {i+1} contains unusually little embedded text; confirm that extraction is complete.")
                    continue
                try:
                    import pytesseract
                    _configure_tesseract(pytesseract)
                    pix=p.get_pixmap(matrix=fitz.Matrix(2,2)); image=Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text=pytesseract.image_to_string(image).strip()
                    if text and ocr_text:
                        native_lines=text.splitlines(); ocr_lines=ocr_text.splitlines()
                        normalized={line.strip().casefold() for line in native_lines}
                        ocr_lines=[line for line in ocr_lines if line.strip().casefold() not in normalized]
                        text="\n".join(native_lines+ocr_lines).strip()
                        extraction="pymupdf+tesseract-ocr"
                    elif ocr_text:
                        text=ocr_text; extraction="tesseract-ocr"
                    else:
                        extraction="pymupdf" if text else "unavailable"
                    pages.append(PageText(page=i+1,text=text,extraction_method=extraction))
                    if sparse and ocr_text: warnings.append(f"Page {i+1} had sparse native text and OCR fallback was used; verify OCR against the page image.")
                    elif sparse: warnings.append(f"Page {i+1} had sparse native text and OCR returned no additional text; review this page.")
                except Exception:
                    pages.append(PageText(page=i+1,text=text,extraction_method="pymupdf" if text else "unavailable"))
                    warnings.append(f"Page {i+1} has no embedded text or only sparse text; OCR is unavailable or failed. Review this page image.")
            return pages,count,warnings
    try:
        import pytesseract
        _configure_tesseract(pytesseract)
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
