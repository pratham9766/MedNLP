import json, logging, mimetypes, uuid, time
from contextlib import asynccontextmanager
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from sqlalchemy import text
from sqlalchemy import inspect
from fastapi import FastAPI, Depends, File, HTTPException, UploadFile, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db import Base, engine, get_db, SessionLocal
from app.models import User, Document, AnalysisResult, ReviewAnnotation, AuditEvent
from app.schemas import QuestionRequest, ReviewRequest, AuthRequest, ExportPayload
from app.security import hash_password, verify_password, issue_token, token_user
from app.services import extract_document_text, answer_report_question, validate_upload_content, UploadValidationError
from app.nlp.extract import process_pages

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("mednlp")
@asynccontextmanager
async def lifespan(_app):
    startup()
    yield

app=FastAPI(title="MedNLP Insight API",version="0.1.0",description="Local research prototype; not for diagnosis.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.trusted_origins,allow_methods=["GET","POST","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type"])

@app.middleware("http")
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("Referrer-Policy","no-referrer")
    response.headers.setdefault("X-Frame-Options","SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
    return response
pool=ThreadPoolExecutor(max_workers=2)
_active_jobs:set[int]=set()
_job_lock=Lock()
_login_failures:dict[str,list[float]]={}
_login_lock=Lock()
MAX_PAGES=settings.max_pages
ALLOWED={"application/pdf":".pdf","image/png":".png","image/jpeg":".jpg"}

def startup():
    if not settings.secret_key or settings.secret_key == "development-only-change-before-use" or len(settings.secret_key) < 32:
        raise RuntimeError("MEDNLP_SECRET_KEY must be configured with at least 32 characters before startup.")
    settings.storage_dir.mkdir(parents=True,exist_ok=True)
    migrate_database(engine)
    # Document status is the durable local queue. Recover work interrupted by a restart.
    with SessionLocal() as db:
        completed=db.query(Document).filter(Document.status.in_(["completed","completed_with_warnings"])).all()
        for document in completed:
            if document.analysis: document.analysis.review_status=report_review_status(document)
        interrupted=db.query(Document).filter(Document.status=="processing").all()
        for document in interrupted: document.status="queued"
        queued=[row.id for row in db.query(Document.id).filter(Document.status=="queued").all()]
        db.commit()
    for document_id in queued:
        try: enqueue_job(document_id)
        except RuntimeError: log.exception("Could not recover queued document id=%s",document_id)

def migrate_database(database_engine):
    """Upgrade a fresh database, or safely baseline-stamp a complete legacy schema."""
    from alembic import command
    from alembic.config import Config
    migration_dir=Path(__file__).resolve().parents[1]
    config=Config(str(migration_dir/"alembic.ini"))
    config.set_main_option("script_location",str(migration_dir/"migrations"))
    with database_engine.connect() as connection:
        config.attributes["connection"]=connection
        tables=set(inspect(connection).get_table_names())
        expected=set(Base.metadata.tables)
        stamp_legacy=False
        if "alembic_version" not in tables and expected.issubset(tables):
            inspector=inspect(connection)
            mismatched=[name for name in expected if not set(Base.metadata.tables[name].columns.keys()).issubset({column["name"] for column in inspector.get_columns(name)})]
            if mismatched:
                raise RuntimeError(f"Existing database tables do not match the initial schema: {', '.join(sorted(mismatched))}.")
            stamp_legacy=True
        elif "alembic_version" not in tables and tables.intersection(expected):
            raise RuntimeError("Database has a partial legacy schema; back it up and resolve its schema before migration.")
        # Inspection starts an implicit SQLAlchemy transaction. End it before
        # giving Alembic the connection, then atomically persist the version row
        # and any upgrade operations on that same connection.
        connection.commit()
        with connection.begin():
            if stamp_legacy:
                command.stamp(config,"head")
            command.upgrade(config,"head")
bearer=HTTPBearer(auto_error=False)

def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    uid=token_user(credentials.credentials) if credentials else None
    user=db.query(User).filter_by(id=uid).first() if uid else None
    if not user: raise HTTPException(401,"Sign in to access reports.",headers={"WWW-Authenticate":"Bearer"})
    return user

@app.post("/api/v1/auth/register",status_code=201)
def register(body:AuthRequest,db:Session=Depends(get_db)):
    if db.query(User).filter_by(username=body.username).first(): raise HTTPException(409,"Username is already registered.")
    user=User(username=body.username,password_hash=hash_password(body.password)); db.add(user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Username is already registered.")
    db.refresh(user)
    return {"access_token":issue_token(user.id),"token_type":"bearer","username":user.username}

@app.post("/api/v1/auth/login")
def login(body:AuthRequest,request:Request,db:Session=Depends(get_db)):
    client_ip=request.client.host if request.client else "unknown"
    now=time.time()
    with _login_lock:
        for address,stamps in list(_login_failures.items()):
            if not any(now-stamp<300 for stamp in stamps): _login_failures.pop(address,None)
        attempts=[stamp for stamp in _login_failures.get(client_ip,[]) if now-stamp<300]
        if len(attempts)>=10: raise HTTPException(429,"Too many unsuccessful sign-in attempts. Try again later.",headers={"Retry-After":"300"})
        _login_failures[client_ip]=attempts+[now]
    user=db.query(User).filter_by(username=body.username).first()
    if not user or not verify_password(body.password,user.password_hash):
        raise HTTPException(401,"Username or password is incorrect.")
    with _login_lock: _login_failures.pop(client_ip,None)
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
            d.status="processing"; db.commit()
            pages,count,warnings=extract_document_text(settings.storage_dir/d.object_key,d.mime_type,settings.max_pages)
            if count>MAX_PAGES: raise ValueError("page_limit")
            result=process_pages(pages,warnings)
            if not any(p.text.strip() for p in pages): result.warnings.append("No readable text was extracted. Configure OCR or upload a text-based document.")
            d.page_count=count; d.document_type=result.document_type; d.status="completed_with_warnings" if result.warnings else "completed"
            d.analysis=AnalysisResult(model_ids=result.model_ids,structured_data=result.model_dump(mode="json"),summary=result.summary,warnings=result.warnings,review_status="needs_review")
            db.add(AuditEvent(actor_id=d.owner_id,action="analysis_completed",resource_id=str(d.id),metadata_json={"status":"completed"})); db.commit()
        except Exception as exc:
            d.status="failed"; d.error_code=str(exc) if str(exc) in ("page_limit",) else "processing_failed"
            db.add(AuditEvent(actor_id=d.owner_id,action="analysis_failed",resource_id=str(d.id),metadata_json={"error_code":d.error_code})); db.commit()
            log.warning("Document processing failed id=%s code=%s",document_id,d.error_code)

def _execute_job(document_id:int):
    try: run_job(document_id)
    finally:
        with _job_lock: _active_jobs.discard(document_id)

def enqueue_job(document_id:int):
    """Schedule one persisted report job per document in this API process."""
    with _job_lock:
        if document_id in _active_jobs: return False
        _active_jobs.add(document_id)
        try: pool.submit(_execute_job,document_id)
        except RuntimeError:
            _active_jobs.discard(document_id)
            raise
    return True

@app.get("/api/v1/health")
def health():
    try:
        import fitz
        pdf=True
    except ImportError: pdf=False
    try:
        import pytesseract
        if settings.tesseract_cmd: pytesseract.pytesseract.tesseract_cmd=settings.tesseract_cmd
        tesseract_path=__import__("shutil").which(pytesseract.pytesseract.tesseract_cmd)
        ocr=bool(tesseract_path and Path(tesseract_path).is_file())
    except ImportError: ocr=False
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
        database="available"
    except Exception:
        database="unavailable"
    return {"status":"ok" if database=="available" else "degraded","database":database,"pdf_text_extraction":pdf,"ocr_available":ocr,"tesseract_path":tesseract_path if 'tesseract_path' in locals() else None,"ocr_setup":"Set MEDNLP_TESSERACT_CMD to the full tesseract.exe path or add tesseract to PATH." if not ocr else None,"llm_provider":"not configured; no external transfer","upload_limits":{"max_upload_bytes":settings.max_upload_bytes,"max_pages":settings.max_pages,"max_image_pixels":40_000_000}}

@app.post("/api/v1/documents",status_code=202)
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(current_user)):
    mime=file.content_type or mimetypes.guess_type(file.filename or "")[0]
    data=await file.read(settings.max_upload_bytes+1)
    try: validate_upload_content(data,mime,settings.max_upload_bytes,MAX_PAGES)
    except UploadValidationError as exc: raise HTTPException(exc.status_code,exc.detail)
    key=uuid.uuid4().hex+ALLOWED[mime]; stored=settings.storage_dir/key
    stored.write_bytes(data)
    d=Document(owner_id=user.id,original_filename=Path(file.filename or "report").name[:255],object_key=key,mime_type=mime,file_size=len(data),status="queued")
    db.add(d); db.add(AuditEvent(actor_id=user.id,action="document_uploaded",resource_id=key,metadata_json={"bytes":len(data)}))
    try:
        db.commit(); db.refresh(d)
    except Exception:
        db.rollback(); stored.unlink(missing_ok=True); raise
    try: enqueue_job(d.id)
    except RuntimeError:
        d.status="failed"; d.error_code="processing_unavailable"; db.commit()
    return {"id":d.id,"status":d.status,"filename":d.original_filename}

def serialize(d):
    return {"id":d.id,"filename":d.original_filename,"mime_type":d.mime_type,"file_size":d.file_size,"document_type":d.document_type,"status":d.status,"page_count":d.page_count,"created_at":d.created_at.isoformat(),"error_code":d.error_code,"review_status":d.analysis.review_status if d.analysis else None}

def report_review_status(document:Document)->str:
    """Derive report review state from processing state and persisted item reviews.

    Warning-bearing extraction remains in the review queue because source coverage may
    be incomplete. A clean completed extraction with no reviewable items is complete.
    """
    if document.status not in {"completed", "completed_with_warnings"} or not document.analysis:
        return "needs_review"
    if document.status != "completed":
        return "needs_review"
    items=document.analysis.structured_data.get("items", [])
    reviewable=[item for item in items if item.get("review_required", True)]
    if all(item.get("review_status") in {"reviewed", "corrected"} for item in reviewable):
        return "reviewed"
    return "needs_review"

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
    d.status="queued"; d.error_code=None; db.commit()
    try: scheduled=enqueue_job(d.id)
    except RuntimeError:
        d.status="failed"; d.error_code="processing_unavailable"; db.commit()
        raise HTTPException(503,"Processing is temporarily unavailable; retry this report later.")
    if not scheduled:
        d.status="failed"; d.error_code="processing_already_active"; db.commit()
        raise HTTPException(409,"This report is already being processed; try again after it finishes.")
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
    response=FileResponse(p,media_type=d.mime_type,filename=d.original_filename,content_disposition_type="inline")
    response.headers["Cache-Control"]="private, no-store"
    return response

@app.post("/api/v1/documents/{document_id}/questions")
def question(document_id:int,request:QuestionRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    pages=d.analysis.structured_data.get("pages",[])
    return answer_report_question(request.question,pages)

@app.post("/api/v1/documents/{document_id}/review")
def review(document_id:int,request:ReviewRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if d.status not in {"completed", "completed_with_warnings"}:
        raise HTTPException(409,"This report has no complete analysis available for review.")
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    data=d.analysis.structured_data; item=next((x for x in data.get("items",[]) if x.get("id")==request.item_id),None)
    if item is None: raise HTTPException(404,"Extracted item not found.")
    if not item.get("review_required",True): raise HTTPException(409,"This extracted item does not require review.")
    original=item.get("normalized_value") or item["original_text"]
    current=item.get("reviewer_correction")
    correction=request.corrected_value
    if not request.reviewed:
        changed=item.get("review_status","needs_review")!="needs_review"
        if changed:
            item["review_status"]="needs_review"
            d.analysis.structured_data=data; flag_modified(d.analysis,"structured_data")
            db.add(AuditEvent(actor_id=user.id,action="entity_review_saved",resource_id=str(d.id),metadata_json={"item_id":request.item_id,"change_type":"reopened"}))
        report_status=report_review_status(d)
        status_changed=d.analysis.review_status!=report_status
        if status_changed: d.analysis.review_status=report_status
        if changed or status_changed:
            db.commit()
        return {"status":"saved","changed":changed,"review_status":item.get("review_status","needs_review")}
    changed=current!=correction or item.get("review_status","needs_review")=="needs_review"
    if changed:
        db.add(ReviewAnnotation(analysis_result_id=d.analysis.id,item_id=request.item_id,original_value=original,corrected_value=correction,reviewer_feedback=request.feedback))
        item["review_status"]="reviewed" if correction==original else "corrected"
        item["reviewer_correction"]=correction
        d.analysis.structured_data=data; flag_modified(d.analysis,"structured_data")
        db.add(AuditEvent(actor_id=user.id,action="entity_review_saved",resource_id=str(d.id),metadata_json={"item_id":request.item_id,"change_type":"reviewed" if correction==original else "corrected"}))
    report_status=report_review_status(d)
    status_changed=d.analysis.review_status!=report_status
    if status_changed: d.analysis.review_status=report_status
    if changed or status_changed:
        db.commit()
    return {"status":"saved","changed":changed,"review_status":item.get("review_status","needs_review")}

@app.get("/api/v1/documents/{document_id}/export",response_model=ExportPayload)
def export(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user)
    if not d.analysis: raise HTTPException(409,"Analysis is not available yet.")
    history=[]
    events=db.query(AuditEvent).filter_by(resource_id=str(d.id),action="entity_review_saved").order_by(AuditEvent.created_at.asc()).all()
    for event in events:
        history.append({"item_id":event.metadata_json.get("item_id"),"reviewer_id":event.actor_id,"change_type":event.metadata_json.get("change_type"),"created_at":event.created_at.isoformat()})
    return ExportPayload(document=serialize(d),analysis=d.analysis.structured_data,warnings=d.analysis.warnings,review_history=history)

@app.delete("/api/v1/documents/{document_id}",status_code=204)
def delete(document_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    d=owner_doc(db,document_id,user); p=settings.storage_dir/d.object_key
    storage=settings.storage_dir.resolve(); resolved=p.resolve()
    if storage not in resolved.parents: raise HTTPException(500,"Stored document path is invalid.")
    quarantined=resolved.with_name(f".{resolved.name}.deleting-{uuid.uuid4().hex}")
    if resolved.exists(): resolved.replace(quarantined)
    db.add(AuditEvent(actor_id=user.id,action="document_deleted",resource_id=str(d.id),metadata_json={"status":"deleted"})); db.delete(d)
    try: db.commit()
    except Exception:
        db.rollback()
        if quarantined.exists(): quarantined.replace(resolved)
        raise
    try: quarantined.unlink(missing_ok=True)
    except OSError: log.error("Document cleanup pending id=%s",document_id)
