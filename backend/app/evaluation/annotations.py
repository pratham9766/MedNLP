"""Versioned, source-grounded annotation models and JSONL validation."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Relation(BaseModel):
    relation_type: str
    target_entity_id: str

class Annotation(BaseModel):
    entity_id: str
    source_page: int = Field(ge=1)
    entity_type: str
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    original_text: str
    normalized_value: str | None = None
    unit: str | None = None
    reference_interval: str | None = None
    negation: bool = False
    uncertainty: bool = False
    temporality: Literal["current", "historical", "unknown"] = "unknown"
    assertion_status: Literal["possible", "likely", "suspected", "considered", "less_likely", "favored", "ruled_out", "uncertain"] | None = None
    medication_name: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    medication_change: Literal["started", "stopped", "dose_increased", "dose_decreased", "dose_changed", "continued", "held", "resumed"] | None = None
    relations: list[Relation] = Field(default_factory=list)
    provenance: str = "manual_synthetic"

    @model_validator(mode="after")
    def valid_span(self):
        if self.end_char <= self.start_char or self.end_char-self.start_char != len(self.original_text):
            raise ValueError("annotation offsets must match original_text length")
        return self

class AnnotatedDocument(BaseModel):
    schema_version: Literal["1.0", "1.1"]
    document_id: str
    patient_group: str
    split: Literal["development", "synthetic_eval"]
    document_type: Literal["laboratory", "discharge", "radiology", "unknown"]
    pages: list[dict]
    annotations: list[Annotation] = Field(default_factory=list)
    provenance: str = "synthetic_authored"
    annotation_review_status: Literal["not_independently_reviewed", "independently_reviewed", "adjudicated"] = "not_independently_reviewed"
    reviewer_id: str | None = None

    @model_validator(mode="after")
    def validate_spans(self):
        by_page = {p["page"]: p["text"] for p in self.pages}
        entity_ids = {a.entity_id for a in self.annotations}
        if len(entity_ids) != len(self.annotations):
            raise ValueError("entity_id values must be unique within a document")
        if self.annotation_review_status == "not_independently_reviewed" and self.reviewer_id is not None:
            raise ValueError("unreviewed annotations cannot claim a reviewer")
        if self.annotation_review_status != "not_independently_reviewed" and not self.reviewer_id:
            raise ValueError("independently reviewed annotations require reviewer_id")
        for annotation in self.annotations:
            page = next((p for p in self.pages if p["page"] == annotation.source_page), None)
            if page is None or page["text"][annotation.start_char:annotation.end_char] != annotation.original_text:
                raise ValueError("annotation span does not match page text")
            if any(rel.target_entity_id not in entity_ids for rel in annotation.relations):
                raise ValueError("relation target must reference an entity in this document")
        return self

