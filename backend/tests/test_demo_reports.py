import json
from pathlib import Path

from app.nlp.extract import process_pages
from app.schemas import Analysis
from app.services import extract_document_text


DEMO_ROOT = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "demo_reports"


def test_synthetic_demo_reports_extract_with_grounded_evidence():
    manifest = json.loads((DEMO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["reports"]) == 8
    assert len(list(DEMO_ROOT.glob("*.pdf"))) == len(manifest["reports"])
    project_readme=(DEMO_ROOT.parents[2] / "README.md").read_text(encoding="utf-8")
    assert "contains eight fictional PDF fixtures" in project_readme
    assert all(report["synthetic"] for report in manifest["reports"])
    assert {report["document_type"] for report in manifest["reports"]} == {"laboratory", "discharge", "radiology"}

    for report in manifest["reports"]:
        pages, page_count, extraction_warnings = extract_document_text(DEMO_ROOT / report["filename"], "application/pdf")
        analysis = process_pages(pages, extraction_warnings)
        Analysis.model_validate(analysis.model_dump())
        assert page_count == report["page_count"] == len(pages)
        assert analysis.document_type == report["document_type"]
        assert len(analysis.items) >= 8
        assert analysis.summary_evidence
        for item in analysis.items:
            assert item.source_page is not None and item.span_start is not None and item.span_end is not None
            page_text = next(page.text for page in pages if page.page == item.source_page)
            assert page_text[item.span_start:item.span_end] == item.original_text


def test_demo_report_pack_disclaims_real_patient_or_clinical_status():
    manifest = json.loads((DEMO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert "fictional" in manifest["disclaimer"].lower()
    for report in manifest["reports"]:
        text = (DEMO_ROOT / report["text_filename"]).read_text(encoding="utf-8")
        assert "not a real patient record" in text.lower()
        assert "medical advice" in text.lower()


def test_detailed_patient_and_differential_cases_are_explicitly_synthetic():
    manifest = json.loads((DEMO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    reports = {report["id"]: report for report in manifest["reports"]}
    patient = reports["demo-complex-patient-discharge-01"]
    differential = reports["demo-differential-workup-01"]

    assert patient["page_count"] == 4
    assert differential["page_count"] == 3
    assert patient["synthetic_identity"] == differential["synthetic_identity"] == "fictional; no real patient data"

    patient_text = (DEMO_ROOT / patient["text_filename"]).read_text(encoding="utf-8").lower()
    differential_text = (DEMO_ROOT / differential["text_filename"]).read_text(encoding="utf-8").lower()
    assert "admission and discharge summary" in patient_text
    assert "medication reconciliation" in patient_text
    assert "differential assessment" in differential_text
    assert "not established" in differential_text
    assert "not a real patient record" in differential_text

def test_long_differential_demo_emits_attributed_possibilities():
    from app.schemas import PageText
    manifest=json.loads((DEMO_ROOT/"manifest.json").read_text(encoding="utf-8"))
    report=next(entry for entry in manifest["reports"] if entry["id"]=="demo-differential-workup-01")
    raw=(DEMO_ROOT/report["text_filename"]).read_text(encoding="utf-8")
    pages=[]
    for page_number,chunk in enumerate(raw.split("--- PAGE ")[1:],start=1):
        _,content=chunk.split("---",1)
        pages.append(PageText(page=page_number,text=content.strip(),extraction_method="synthetic-text-fixture"))
    analysis=process_pages(pages)
    assert len(analysis.differential_possibilities)==5
    by_id={item.id:item for item in analysis.items}
    for possibility in analysis.differential_possibilities:
        assert possibility.source_evidence_ids
        for evidence_id in possibility.source_evidence_ids+possibility.evidence_for+possibility.evidence_against:
            item=by_id[evidence_id]
            source=next(page.text for page in pages if page.page==item.source_page)
            assert source[item.span_start:item.span_end]==item.original_text
