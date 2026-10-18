import json, logging, mimetypes, uuid
from contextlib import asynccontextmanager
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.core.config import settings
from app.db import Base, engine, get_db, SessionLocal
from app.models import User, Document, AnalysisResult, ReviewAnnotation, AuditEvent
from app.schemas import QuestionRequest, ReviewRequest, AuthRequest
from app.security import hash_password, verify_password, issue_token, token_user
from app.services import extract_document_text, answer_report_question
from app.nlp.extract import process_pages

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("mednlp")
@asynccontextmanager
async def lifespan(_app):
    startup()
    yield

app=FastAPI(title="MedNLP Insight API",version="0.1.0",description="Local research prototype; not for diagnosis.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173"],allow_methods=["*"],allow_headers=["*"])
pool=ThreadPoolExecutor(max_workers=2)
MAX_PAGES=100
ALLOWED={"application/pdf":".pdf","image/png":".png","image/jpeg":".jpg"}

def startup():
    settings.storage_dir.mkdir(parents=True,exist_ok=True)
    Base.metadata.create_all(bind=engine)
bearer=HTTPBearer(auto_error=False)

def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    uid=token_user(credentials.credentials) if credentials else None
    user=db.query(User).filter_by(id=uid).first() if uid else None
    if not user: raise HTTPException(401,"Sign in to access reports.",headers={"WWW-Authenticate":"Bearer"})
    return user

@app.post("/api/v1/auth/register",status_code=201)
def register(body:AuthRequest,db:Session=Depends(get_db)):
    if db.query(User).filter_by(username=body.username).first(): raise HTTPException(409,"Username is already registered.")
    user=User(username=body.username,password_hash=hash_password(body.password)); db.add(user); db.commit(); db.refresh(user)
    return {"access_token":issue_token(user.id),"token_type":"bearer","username":user.username}

@app.post("/api/v1/auth/login")
def login(body:AuthRequest,db:Session=Depends(get_db)):
    user=db.query(User).filter_by(username=body.username).first()
    if not user or not verify_password(body.password,user.password_hash): raise HTTPException(401,"Username or password is incorrect.")
    return {"access_token":issue_token(user.id),"token_type":"bearer","username":user.username}

def owner_doc(db:Session,doc_id:int,user:User):
    d=db.query(Document).filter_by(id=doc_id,owner_id=user.id).first()
    if not d: raise HTTPException(404,"Document not found")
    return d

def run_job(document_id:int):
    with SessionLocal() as db:
        d=db.query(Document).filter_by(id=document_id).first()
        if not d: return
        try:
            pages,count,warnings=extract_document_text(settings.storage_dir/d.object_key,d.mime_type)
            if count>MAX_PAGES: raise ValueError("page_limit")
            result=process_pages(pages,warnings)
            if not any(p.text.strip() for p in pages): result.warnings.append("No readable text was extracted. Configure OCR or upload a text-based document.")
            d.page_count=count; d.document_type=result.document_type; d.status="completed"
            d.analysis=AnalysisResult(model_ids=result.model_ids,structured_data=result.model_dump(mode="json"),summary=result.summary,warnings=result.warnings,review_status="needs_review")
            db.add(AuditEvent(actor_id=d.owner_id,action="analysis_completed",resource_id=str(d.id),metadata_json={"status":"completed"})); db.commit()
        except Exception as exc:
            d.status="failed"; d.error_code=str(exc) if str(exc) in ("page_limit",) else "processing_failed"
            db.add(AuditEvent(actor_id=d.owner_id,action="analysis_failed",resource_id=str(d.id),metadata_json={"error_code":d.error_code})); db.commit()
            log.warning("Document processing failed id=%s code=%s",document_id,d.error_code)

@app.get("/api/v1/health")
def health():
    try:
        import fitz
        pdf=True
    except ImportError: pdf=False
    try:
        import pytesseract
        ocr=bool(__import__("shutil").which("tesseract"))
    except ImportError: ocr=False
    return {"status":"ok","database":"configured","pdf_text_extraction":pdf,"ocr_available":ocr,"llm_provider":"not configured; no external transfer"}

@app.post("/api/v1/documents",status_code=202)
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(current_user)):
    mime=file.content_type or mimetypes.guess_type(file.filename or "")[0]
    if mime not in ALLOWED: raise HTTPException(415,"Supported formats are PDF, PNG, and JPEG.")
    data=await file.read(settings.max_upload_bytes+1)
    if not data: raise HTTPException(400,"The uploaded file is empty.")
    if len(data)>settings.max_upload_bytes: raise HTTPException(413,"File exceeds the configured upload size limit.")
    if mime=="application/pdf" and not data.startswith(b"%PDF-"): raise HTTPException(400,"The file does not appear to be a valid PDF.")
    if mime=="image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"): raise HTTPException(400,"The file does not appear to be a valid PNG.")
    if mime=="image/jpeg" and not data.startswith(b"\xff\xd8\xff"): raise HTTPException(400,"The file does not appear to be a valid JPEG.")
    key=uuid.uuid4().hex+ALLOWED[mime]; (settings.storage_dir/key).write_bytes(data)
    d=Document(owner_id=user.id,original_filename=Path(file.filename or "report").name[:255],object_key=key,mime_type=mime,file_size=len(data),status="queued")
    db.add(d); db.add(AuditEvent(actor_id=user.id,action="document_uploaded",resource_id=key,metadata_json={"bytes":len(data)})); db.commit(); db.refresh(d)
    pool.submit(run_job,d.id)
    return {"id":d.id,"status":d.status,"filename":d.original_filename}

def serialize(d):
    return {"id":d.id,"filename":d.original_filename,"mime_type":d.mime_type,"file_size":d.file_size,"document_type":d.document_type,"status":d.status,"page_count":d.page_count,"created_at":d.created_at.isoformat(),"error_code":d.error_code,"review_status":d.analysis.review_status if d.analysis else None}

@app.get("/api/v1/documents")
def list_documents(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [serialize(d) for d in db.query(Document).filter_by(owner_id=user.id).order_by(Document.created_at.desc()).limit(200).all()]

@app.get("/api/v1/documents/{document_id}")
def get_document(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)): return serialize(owner_doc(db,document_id,user))

@app.get("/api/v1/documents/{document_id}/status")
def status(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user); return {"id":d.id,"status":d.status,"error_code":d.error_code}

@app.post("/api/v1/documents/{document_id}/retry",status_code=202)
def retry(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if d.status!="failed": raise HTTPException(409,"Only failed processing jobs can be retried.")
    d.status="queued"; d.error_code=None; db.commit(); pool.submit(run_job,d.id)
    return {"id":d.id,"status":d.status}

@app.get("/api/v1/documents/{document_id}/analysis")
def analysis(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if d.status in ("queued","processing"): raise HTTPException(409,"Analysis is still processing.")
    if not d.analysis: raise HTTPException(409,"No analysis is available for this document.")
    return d.analysis.structured_data

@app.get("/api/v1/documents/{document_id}/file")
def document_file(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user); p=settings.storage_dir/d.object_key
    if not p.is_file(): raise HTTPException(404,"Document file is unavailable.")
    return FileResponse(p,media_type=d.mime_type,filename=d.original_filename,content_disposition_type="inline")

@app.post("/api/v1/documents/{document_id}/questions")
def question(document_id:int,request:QuestionRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    pages=d.analysis.structured_data.get("pages",[])
    return answer_report_question(request.question,pages)

@app.post("/api/v1/documents/{document_id}/review")
def review(document_id:int,request:ReviewRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    data=d.analysis.structured_data; item=next((x for x in data.get("items",[]) if x.get("id")==request.item_id),None)
    if item is None: raise HTTPException(404,"Extracted item not found.")
    db.add(ReviewAnnotation(analysis_result_id=d.analysis.id,item_id=request.item_id,original_value=item.get("normalized_value") or item["original_text"],corrected_value=request.corrected_value,reviewer_feedback=request.feedback))
    item["review_status"]="reviewed"; item["reviewer_correction"]=request.corrected_value
    d.analysis.structured_data=data; flag_modified(d.analysis,"structured_data"); d.analysis.review_status="reviewed"; db.commit(); return {"status":"saved"}

@app.get("/api/v1/documents/{document_id}/export")
def export(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    return {"document":serialize(d),"analysis":d.analysis.structured_data,"warnings":d.analysis.warnings}

@app.delete("/api/v1/documents/{document_id}",status_code=204)
def delete(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user); p=settings.storage_dir/d.object_key
    if p.exists(): p.unlink()
    db.add(AuditEvent(actor_id=1,action="document_deleted",resource_id=str(d.id),metadata_json={"status":"deleted"})); db.delete(d); db.commit()
