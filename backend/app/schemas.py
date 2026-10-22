from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

DocType = Literal["laboratory", "discharge", "radiology", "unknown"]
ComparisonStatus = Literal["within_reported_range", "below_reported_range", "above_reported_range", "comparison_unavailable"]
class EvidenceItem(BaseModel):
    id: str
    entity_type: str
    original_text: str
    analyte: str | None = None
    numeric_value: float | None = None
    comparator: Literal["<", ">", "≤", "≥"] | None = None
    qualitative_value: str | None = None
    medication_name: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    medication_change: Literal["started", "stopped", "dose_increased", "dose_decreased", "dose_changed", "continued", "held", "resumed"] | None = None
    modality: str | None = None
    body_region: str | None = None
    report_section: Literal["findings", "impression", "recommendations", "other"] | None = None
    normalized_value: str | None = None
    unit: str | None = None
    reference_interval: str | None = None
    lab_reported_flag: str | None = None
    abnormal_flag: str | None = None
    comparison_status: ComparisonStatus = "comparison_unavailable"
    comparison_note: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    source_page: int | None = None
    source_text: str
    span_start: int | None = None
    span_end: int | None = None
    extraction_method: str = "deterministic-rules-v1"
    provenance: str = "source_text"
    schema_version: str = "1.1"
    negated: bool = False
    uncertain: bool = False
    temporality: Literal["current", "historical", "unknown"] = "unknown"
    review_required: bool = True
    review_status: str = "needs_review"
    reviewer_correction: str | None = None
    validation_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_comparison(self):
        bounds = (self.reference_low, self.reference_high)
        if (bounds[0] is None) != (bounds[1] is None):
            raise ValueError("reference comparison bounds must be supplied together")
        if self.comparison_status == "comparison_unavailable":
            if any(value is not None for value in bounds):
                raise ValueError("unavailable comparisons cannot expose numeric range bounds")
            return self
        if self.entity_type != "laboratory_result" or self.numeric_value is None or not self.unit or self.comparator or self.qualitative_value:
            raise ValueError("a numeric range comparison requires a numeric laboratory result, unit, and no comparator")
        low, high = bounds
        if low is None or high is None or low >= high:
            raise ValueError("a numeric range comparison requires valid lower and upper bounds")
        expected = "below_reported_range" if self.numeric_value < low else "above_reported_range" if self.numeric_value > high else "within_reported_range"
        if expected != self.comparison_status:
            raise ValueError("comparison status does not agree with the reported value and interval bounds")
        return self

class SummaryEvidence(BaseModel):
    statement: str
    source_page: int
    quote: str
    span_start: int
    span_end: int

class PatientOverviewStatement(BaseModel):
    text: str
    source_evidence_ids: list[str] = Field(min_length=1)
    source_page: int
    original_text: str
    explanation: str | None = None

class PatientOverviewSection(BaseModel):
    key: Literal["findings", "possibilities", "negative_findings", "history", "medications", "recommendations", "clarifications"]
    title: str
    statements: list[PatientOverviewStatement] = Field(default_factory=list)

class DifferentialPossibility(BaseModel):
    possibility_text: str
    normalized_label: str | None = None
    assertion_status: Literal["possible", "likely", "suspected", "considered", "less_likely", "favored", "ruled_out", "uncertain"] = "uncertain"
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    uncertainty_text: str | None = None
    follow_up_text: str | None = None
    source_evidence_ids: list[str] = Field(min_length=1)
    review_required: bool = True

class PageText(BaseModel):
    page: int
    text: str
    extraction_method: str
class Analysis(BaseModel):
    schema_version: str = "1.1"
    document_type: DocType
    items: list[EvidenceItem]
    pages: list[PageText]
    summary: str
    warnings: list[str]
    classification_evidence: dict[str, int] = Field(default_factory=dict)
    summary_evidence: list[SummaryEvidence] = Field(default_factory=list)
    patient_overview: list[PatientOverviewSection] = Field(default_factory=list)
    differential_possibilities: list[DifferentialPossibility] = Field(default_factory=list)
    summary_method: str = "deterministic-evidence-overview-v2"
    model_ids: list[str] = ["deterministic-rules-v1"]

    @model_validator(mode="after")
    def validate_evidence(self):
        pages = {p.page: p.text for p in self.pages}
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("entity IDs must be unique within an analysis")
        for item in self.items:
            if item.source_page is None:
                if item.span_start is not None or item.span_end is not None:
                    raise ValueError("an evidence span requires a source page")
                continue
            source = pages.get(item.source_page)
            if source is None:
                raise ValueError("evidence references a page absent from the source report")
            if (item.span_start is None) != (item.span_end is None):
                raise ValueError("evidence offsets must be supplied as a pair")
            if item.span_start is not None and (item.span_start < 0 or item.span_end <= item.span_start or source[item.span_start:item.span_end] != item.original_text):
                raise ValueError("entity offsets must resolve to original_text in source page")
        for evidence in self.summary_evidence:
            source = pages.get(evidence.source_page)
            if source is None or evidence.span_start < 0 or evidence.span_end <= evidence.span_start or source[evidence.span_start:evidence.span_end] != evidence.quote:
                raise ValueError("summary evidence offsets must resolve to the quoted source text")
        known_ids=set(ids)
        for section in self.patient_overview:
            for statement in section.statements:
                if not statement.source_evidence_ids or not set(statement.source_evidence_ids).issubset(known_ids):
                    raise ValueError("patient overview statements must reference extracted evidence")
                sources=[item for item in self.items if item.id in statement.source_evidence_ids]
                if not any(item.source_page==statement.source_page and item.original_text==statement.original_text for item in sources):
                    raise ValueError("patient overview wording must retain a linked source passage")
        for possibility in self.differential_possibilities:
            refs=set(possibility.source_evidence_ids+possibility.evidence_for+possibility.evidence_against)
            if not possibility.source_evidence_ids or not refs.issubset(known_ids):
                raise ValueError("differential possibilities must reference extracted source evidence")
        return self
class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
class ReviewRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    corrected_value: str = Field(min_length=1, max_length=2000)
    feedback: str = Field(default="", max_length=2000)
    reviewed: bool = True

    @field_validator("corrected_value")
    @classmethod
    def nonblank_correction(cls, value: str) -> str:
        value=value.strip()
        if not value: raise ValueError("correction cannot be blank")
        return value
class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=12, max_length=200)

class ExportDocument(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    document_type: str
    status: str
    page_count: int
    created_at: str
    error_code: str | None = None
    review_status: str | None = None

class ExportReviewEntry(BaseModel):
    item_id: str
    reviewer_id: int | None = None
    change_type: Literal["reviewed", "corrected", "reopened"]
    created_at: str

class ExportPayload(BaseModel):
    schema_version: Literal["1.1"] = "1.1"
    document: ExportDocument
    analysis: Analysis
    warnings: list[str]
    review_history: list[ExportReviewEntry] = Field(default_factory=list)
