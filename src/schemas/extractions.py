from pydantic import BaseModel
import uuid
from typing import Any, Optional
from datetime import datetime


class ExtractionSummary(BaseModel):
    tables: int
    statistics: int
    ocr_used: bool
    advanced_features: bool


class DataExtractionResponse(BaseModel):
    message: str
    document_id: uuid.UUID
    extraction_ids: list[uuid.UUID]
    extraction_summary: ExtractionSummary
    extraction_data: dict[str, Any]


class ExtractionData(BaseModel):
    id: uuid.UUID
    data: dict[str, Any]
    confidence_score: Optional[float]
    created_at: Optional[str]


class DocumentExtractionsResponse(BaseModel):
    document_id: uuid.UUID
    document_filename: str
    extraction_status: str
    extraction_summary: Optional[dict]
    extractions: dict[str, list[ExtractionData]]
    total_extractions: int


class AnalyzeExtractionResponse(BaseModel):
    ai_response: str