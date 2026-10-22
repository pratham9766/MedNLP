import asyncio, time
import pymupdf as fitz
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import db as database
from app import main
from app.models import User
from app.core.config import settings
from app.security import verify_password

class APIClient:
    def request(self, method, path, **kwargs):
        async def send():
            transport=httpx.ASGITransport(app=main.app)
            async with httpx.AsyncClient(transport=transport,base_url="http://test") as c:
                return await c.request(method,path,**kwargs)
        return asyncio.run(send())
    def get(self,path,**kwargs):return self.request("GET",path,**kwargs)
    def post(self,path,**kwargs):return self.request("POST",path,**kwargs)
    def delete(self,path,**kwargs):return self.request("DELETE",path,**kwargs)

@pytest.fixture
def client(tmp_path, monkeypatch):
    path=tmp_path/"test.sqlite"
    engine=create_engine(f"sqlite:///{path.as_posix()}",connect_args={"check_same_thread":False})
    database.Base.metadata.create_all(engine)
    Session=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(database,"engine",engine); monkeypatch.setattr(database,"SessionLocal",Session)
    monkeypatch.setattr(main,"engine",engine); monkeypatch.setattr(main,"SessionLocal",Session)
    main._login_failures.clear()
    monkeypatch.setattr(settings,"storage_dir",tmp_path/"uploads")
    settings.storage_dir.mkdir(parents=True,exist_ok=True)
    main.startup()
    yield APIClient()
    database.Base.metadata.drop_all(engine); engine.dispose()

def register(c,username):
    r=c.post("/api/v1/auth/register",json={"username":username,"password":"test-password-long-123"})
    assert r.status_code==201
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def make_pdf(text):
    doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),text); return doc.tobytes()

def wait_status(c,doc_id,headers,expected):
    for _ in range(100):
        r=c.get(f"/api/v1/documents/{doc_id}/status",headers=headers)
        if r.json()["status"]==expected:return r.json()
        time.sleep(.03)
    pytest.fail(f"document did not reach {expected}: {r.json()}")

def test_authenticated_lab_workflow_and_ownership(client):
    owner=register(client,"alice")
    with database.SessionLocal() as session:
        alice=session.query(User).filter_by(username="alice").one()
        assert alice.password_hash!="test-password-long-123" and verify_password("test-password-long-123",alice.password_hash)
    other=register(client,"bob")
    raw=make_pdf("LABORATORY RESULTS\nGlucose 106 mg/dL H (70-99)\nHemoglobin 13.4 g/dL (12.0-16.0)")
    uploaded=client.post("/api/v1/documents",headers=owner,files={"file":("synthetic-lab.pdf",raw,"application/pdf")})
    assert uploaded.status_code==202
    doc_id=uploaded.json()["id"]
    wait_status(client,doc_id,owner,"completed")
    with database.SessionLocal() as session:
        stored_path=settings.storage_dir/session.query(main.Document).filter_by(id=doc_id).one().object_key
        assert stored_path.is_file()
    analysis=client.get(f"/api/v1/documents/{doc_id}/analysis",headers=owner).json()
    assert analysis["document_type"]=="laboratory"
    glucose=next(x for x in analysis["items"] if "Glucose" in x["original_text"])
    assert glucose["unit"]=="mg/dL" and glucose["reference_interval"]=="70-99"
    assert glucose["lab_reported_flag"]=="H" and glucose["abnormal_flag"]=="high"
    assert glucose["source_page"]==1 and glucose["source_text"] in analysis["pages"][0]["text"]
    assert analysis["summary_evidence"] and analysis["summary_evidence"][0]["quote"]
    found=client.post(f"/api/v1/documents/{doc_id}/questions",headers=owner,json={"question":"What was the glucose result?"}).json()
    assert found["evidence"] and "106" in found["evidence"][0]["quote"]
    absent=client.post(f"/api/v1/documents/{doc_id}/questions",headers=owner,json={"question":"Which antibiotic was prescribed?"}).json()
    assert absent["evidence"]==[] and "not contain enough" in absent["answer"]
    review=client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":glucose["id"],"corrected_value":"Reviewed value: 106 mg/dL","feedback":"Synthetic review"})
    assert review.status_code==200
    assert review.json()["review_status"]=="corrected"
    assert client.get(f"/api/v1/documents/{doc_id}",headers=owner).json()["review_status"]=="needs_review"
    duplicate=client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":glucose["id"],"corrected_value":"Reviewed value: 106 mg/dL","feedback":"Synthetic review"})
    assert duplicate.status_code==200 and duplicate.json()["changed"] is False
    reviewed=client.get(f"/api/v1/documents/{doc_id}/analysis",headers=owner).json()
    reviewed_glucose=next(x for x in reviewed["items"] if x["id"]==glucose["id"])
    assert reviewed_glucose["reviewer_correction"]=="Reviewed value: 106 mg/dL"
    assert reviewed_glucose["original_text"]==glucose["original_text"]
    exported=client.get(f"/api/v1/documents/{doc_id}/export",headers=owner)
    assert exported.status_code==200
    assert exported.json()["schema_version"]=="1.1"
    exported_glucose=next(x for x in exported.json()["analysis"]["items"] if x["id"]==glucose["id"])
    assert exported_glucose["reviewer_correction"]==reviewed_glucose["reviewer_correction"]
    other_item=next(x for x in reviewed["items"] if x["id"]!=glucose["id"])
    assert client.post(f"/api/v1/documents/{doc_id}/review",headers=other,json={"item_id":other_item["id"],"corrected_value":other_item["original_text"]}).status_code==404
    final_review=client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":other_item["id"],"corrected_value":other_item["original_text"]})
    assert final_review.status_code==200
    assert client.get(f"/api/v1/documents/{doc_id}",headers=owner).json()["review_status"]=="reviewed"
    reopened=client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":other_item["id"],"corrected_value":other_item["original_text"],"reviewed":False})
    assert reopened.status_code==200 and reopened.json()["review_status"]=="needs_review"
    assert client.get(f"/api/v1/documents/{doc_id}",headers=owner).json()["review_status"]=="needs_review"
    client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":other_item["id"],"corrected_value":other_item["original_text"]})
    exported=client.get(f"/api/v1/documents/{doc_id}/export",headers=owner)
    assert len(exported.json()["review_history"])==4 and exported.json()["review_history"][2]["change_type"]=="reopened"
    assert exported.json()["review_history"][0]["reviewer_id"] is not None
    assert client.get(f"/api/v1/documents/{doc_id}",headers=other).status_code==404
    assert client.get(f"/api/v1/documents/{doc_id}/file",headers=other).status_code==404
    assert client.delete(f"/api/v1/documents/{doc_id}",headers=owner).status_code==204
    assert not stored_path.exists()
    assert client.get(f"/api/v1/documents/{doc_id}",headers=owner).status_code==404

def test_upload_rejects_mime_mismatch_and_retry_recovers_processing_failure(client,monkeypatch):
    owner=register(client,"charlie")
    invalid=client.post("/api/v1/documents",headers=owner,files={"file":("fake.pdf",b"not a pdf","application/pdf")})
    assert invalid.status_code==400
    def fail_processing(*_args,**_kwargs): raise RuntimeError("synthetic processing failure")
    monkeypatch.setattr(main,"extract_document_text",fail_processing)
    accepted=client.post("/api/v1/documents",headers=owner,files={"file":("synthetic.pdf",make_pdf("LABORATORY RESULTS"),"application/pdf")})
    assert accepted.status_code==202
    doc_id=accepted.json()["id"]
    wait_status(client,doc_id,owner,"failed")
    assert client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":"missing","corrected_value":"reviewed"}).status_code==409
    assert client.post(f"/api/v1/documents/{doc_id}/retry",headers=owner).status_code==202
    wait_status(client,doc_id,owner,"failed")

def test_startup_recovers_persisted_interrupted_jobs(client,monkeypatch):
    from app.models import Document, AnalysisResult
    with database.SessionLocal() as session:
        user=User(username="recovery-user",password_hash="synthetic-hash")
        session.add(user); session.commit(); session.refresh(user)
        queued=Document(owner_id=user.id,original_filename="queued.pdf",object_key="queued-key.pdf",mime_type="application/pdf",file_size=1,status="queued")
        processing=Document(owner_id=user.id,original_filename="processing.pdf",object_key="processing-key.pdf",mime_type="application/pdf",file_size=1,status="processing")
        stale_review=Document(owner_id=user.id,original_filename="review.pdf",object_key="review-key.pdf",mime_type="application/pdf",file_size=1,status="completed",analysis=AnalysisResult(review_status="reviewed",structured_data={"items":[{"id":"done","review_status":"reviewed"},{"id":"pending","review_status":"needs_review"}]}))
        session.add_all([queued,processing,stale_review]);session.commit()
        queued_id,processing_id,review_id=queued.id,processing.id,stale_review.id
    submitted=[]
    monkeypatch.setattr(main,"enqueue_job",lambda document_id: submitted.append(document_id))
    main.startup()
    assert set(submitted)=={queued_id,processing_id}
    with database.SessionLocal() as session:
        assert session.query(Document).filter_by(id=processing_id).one().status=="queued"
        assert session.query(Document).filter_by(id=review_id).one().analysis.review_status=="needs_review"

def test_upload_filename_never_becomes_storage_path(client):
    owner=register(client,"path-user")
    response=client.post("/api/v1/documents",headers=owner,files={"file":("..\\..\\outside.pdf",make_pdf("unknown notes"),"application/pdf")})
    assert response.status_code==202 and response.json()["filename"]=="outside.pdf"
    with database.SessionLocal() as session:
        doc=session.query(main.Document).filter_by(id=response.json()["id"]).one()
        assert "/" not in doc.object_key and "\\" not in doc.object_key and doc.object_key!="outside.pdf"
def test_discharge_and_radiology_pipeline_basics():
    from app.nlp.extract import process_pages
    from app.schemas import PageText
    discharge=process_pages([PageText(page=1,text="DISCHARGE SUMMARY\nDiagnosis: pneumonia.\nMedication: amoxicillin 500 mg daily.\nFollow-up in 7 days.",extraction_method="fixture")])
    radiology=process_pages([PageText(page=1,text="CT scan\nFindings: No pleural effusion.\nImpression: No acute process.",extraction_method="fixture")])
    assert discharge.document_type=="discharge" and any(x.entity_type=="medication" for x in discharge.items)
    assert radiology.document_type=="radiology" and any("No acute process" in x.original_text for x in radiology.items)

def test_health_reports_available_components(client):
    response=client.get("/api/v1/health")
    assert response.status_code==200
    assert response.json()["status"]=="ok" and response.json()["pdf_text_extraction"] is True
    assert response.headers["x-content-type-options"]=="nosniff"
    assert response.json()["database"]=="available"

def test_login_throttles_repeated_failures(client):
    body={"username":"missing-user","password":"wrong-password-long"}
    for _ in range(10):
        assert client.post("/api/v1/auth/login",json=body).status_code==401
    limited=client.post("/api/v1/auth/login",json=body)
    assert limited.status_code==429 and limited.headers["retry-after"]=="300"

def test_ocr_executable_failure_is_reported_without_crashing(tmp_path,monkeypatch):
    from PIL import Image
    import pytesseract
    from app.services import extract_document_text
    path=tmp_path/"synthetic.png"; Image.new("RGB",(12,12),"white").save(path)
    def unavailable(*_args,**_kwargs):raise pytesseract.TesseractNotFoundError()
    monkeypatch.setattr(pytesseract,"image_to_string",unavailable)
    pages,count,warnings=extract_document_text(path,"image/png")
    assert count==1 and pages[0].text=="" and warnings and pages[0].extraction_method=="unavailable"

def test_token_signature_rejects_tampering():
    from app.security import issue_token, token_user
    token=issue_token(123)
    assert token_user(token)==123
    assert token_user(token[:-1]+("A" if token[-1]!="A" else "B")) is None

def test_export_contract_keeps_correction_and_source_evidence():
    from app.schemas import Analysis, ExportPayload
    source="Glucose 106 mg/dL"
    payload={"schema_version":"1.1","document":{"id":1,"filename":"synthetic.pdf","mime_type":"application/pdf","file_size":10,"document_type":"laboratory","status":"completed","page_count":1,"created_at":"2026-01-01T00:00:00+00:00","error_code":None,"review_status":"reviewed"},"analysis":{"schema_version":"1.0","document_type":"laboratory","items":[{"id":"e1","entity_type":"laboratory_result","original_text":source,"normalized_value":"106 mg/dL","source_page":1,"source_text":source,"span_start":0,"span_end":len(source),"review_status":"corrected","reviewer_correction":"106 mg/dL checked"}],"pages":[{"page":1,"text":source,"extraction_method":"fixture"}],"summary":"Source text.","warnings":[],"summary_evidence":[{"statement":"The report states: Glucose 106 mg/dL","source_page":1,"quote":source,"span_start":0,"span_end":len(source)}]},"warnings":[],"review_history":[{"item_id":"e1","reviewer_id":4,"change_type":"corrected","created_at":"2026-01-01T00:00:00+00:00"}]}
    export=ExportPayload.model_validate(payload).model_dump(mode="json")
    assert export["analysis"]["items"][0]["reviewer_correction"]=="106 mg/dL checked"
    assert export["review_history"][0]["reviewer_id"]==4

def test_report_review_status_requires_clean_completed_processing():
    from app.main import report_review_status
    from app.models import Document, AnalysisResult
    empty=Document(status="completed",analysis=AnalysisResult(structured_data={"items":[]}))
    assert report_review_status(empty)=="reviewed"  # documented zero-item policy
    partial=Document(status="completed_with_warnings",analysis=AnalysisResult(structured_data={"items":[]}))
    assert report_review_status(partial)=="needs_review"
    failed=Document(status="failed",analysis=AnalysisResult(structured_data={"items":[]}))
    assert report_review_status(failed)=="needs_review"
    mixed=Document(status="completed",analysis=AnalysisResult(structured_data={"items":[
        {"id":"one","review_status":"reviewed"},{"id":"two","review_status":"needs_review"},{"id":"three","review_status":"needs_review"}
    ]}))
    assert report_review_status(mixed)=="needs_review"
    no_reviewable=Document(status="completed",analysis=AnalysisResult(structured_data={"items":[{"id":"ignored","review_required":False}]}))
    assert report_review_status(no_reviewable)=="reviewed"
