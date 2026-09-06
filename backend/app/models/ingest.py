from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.source import SourceChunk

class TextIngestRequest(BaseModel):
    """Request payload for direct pasted text ingestion."""
    text: str = Field(..., min_length=10, description="Raw source text to ingest and segment")
    title: Optional[str] = Field(None, description="Optional label or title for the document")

class IngestResponse(BaseModel):
    """Unified response containing extracted statistics and segmented SourceChunk objects."""
    source_type: str = Field(..., description="Source format: 'text', 'txt', 'pdf'")
    filename: Optional[str] = Field(None, description="Original filename if uploaded")
    character_count: int = Field(..., ge=0, description="Total characters in sanitized source")
    word_count: int = Field(..., ge=0, description="Total words in sanitized source")
    chunk_count: int = Field(..., ge=0, description="Total semantic chunks produced")
    chunks: List[SourceChunk] = Field(..., description="Ordered list of addressable SourceChunk objects")
