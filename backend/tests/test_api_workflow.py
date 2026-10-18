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
    found=client.post(f"/api/v1/documents/{doc_id}/questions",headers=owner,json={"question":"What was the glucose result?"}).json()
    assert found["evidence"] and "106" in found["evidence"][0]["quote"]
    absent=client.post(f"/api/v1/documents/{doc_id}/questions",headers=owner,json={"question":"Which antibiotic was prescribed?"}).json()
    assert absent["evidence"]==[] and "not contain enough" in absent["answer"]
    review=client.post(f"/api/v1/documents/{doc_id}/review",headers=owner,json={"item_id":glucose["id"],"corrected_value":"Reviewed value: 106 mg/dL","feedback":"Synthetic review"})
    assert review.status_code==200
    reviewed=client.get(f"/api/v1/documents/{doc_id}/analysis",headers=owner).json()
    reviewed_glucose=next(x for x in reviewed["items"] if x["id"]==glucose["id"])
    assert reviewed_glucose["reviewer_correction"]=="Reviewed value: 106 mg/dL"
    assert reviewed_glucose["original_text"]==glucose["original_text"]
    exported=client.get(f"/api/v1/documents/{doc_id}/export",headers=owner)
    assert exported.status_code==200
    exported_glucose=next(x for x in exported.json()["analysis"]["items"] if x["id"]==glucose["id"])
    assert exported_glucose["reviewer_correction"]==reviewed_glucose["reviewer_correction"]
    assert client.get(f"/api/v1/documents/{doc_id}",headers=other).status_code==404
    assert client.get(f"/api/v1/documents/{doc_id}/file",headers=other).status_code==404
    assert client.delete(f"/api/v1/documents/{doc_id}",headers=owner).status_code==204
    assert not stored_path.exists()
    assert client.get(f"/api/v1/documents/{doc_id}",headers=owner).status_code==404

def test_upload_rejects_mime_mismatch_and_retry_failure_state(client):
    owner=register(client,"charlie")
    invalid=client.post("/api/v1/documents",headers=owner,files={"file":("fake.pdf",b"not a pdf","application/pdf")})
    assert invalid.status_code==400
    malformed=client.post("/api/v1/documents",headers=owner,files={"file":("broken.pdf",b"%PDF-not-valid","application/pdf")})
    assert malformed.status_code==202
    doc_id=malformed.json()["id"]
    wait_status(client,doc_id,owner,"failed")
    assert client.post(f"/api/v1/documents/{doc_id}/retry",headers=owner).status_code==202
    wait_status(client,doc_id,owner,"failed")

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
