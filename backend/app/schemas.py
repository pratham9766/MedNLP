from typing import Any, Literal
from pydantic import BaseModel, Field

DocType = Literal["laboratory", "discharge", "radiology", "unknown"]
class EvidenceItem(BaseModel):
    id: str
    entity_type: str
    original_text: str
    normalized_value: str | None = None
    unit: str | None = None
    reference_interval: str | None = None
    lab_reported_flag: str | None = None
    abnormal_flag: str | None = None
    source_page: int | None = None
    source_text: str
    span_start: int | None = None
    span_end: int | None = None
    negated: bool = False
    uncertain: bool = False
    temporality: Literal["current", "historical", "unknown"] = "unknown"
    review_status: str = "needs_review"
    validation_warnings: list[str] = Field(default_factory=list)
class PageText(BaseModel):
    page: int
    text: str
    extraction_method: str
class Analysis(BaseModel):
    schema_version: str = "1.0"
    document_type: DocType
    items: list[EvidenceItem]
    pages: list[PageText]
    summary: str
    warnings: list[str]
    model_ids: list[str] = ["deterministic-rules-v1"]
class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
class ReviewRequest(BaseModel):
    item_id: str
    corrected_value: str = Field(min_length=1, max_length=2000)
    feedback: str = Field(default="", max_length=2000)
class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=12, max_length=200)
