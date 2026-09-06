from typing import Optional
from pydantic import BaseModel, Field

class SourceChunk(BaseModel):
    """Represents an addressable segment/chunk of source material with location metadata."""
    chunk_id: str = Field(..., min_length=1, description="Unique chunk identifier (e.g. 'chunk_1')")
    text: str = Field(..., min_length=1, description="Raw text content of the chunk")
    page_number: Optional[int] = Field(None, ge=1, description="Origin page number if extracted from document")
    source_location: Optional[str] = Field(None, description="Section heading or structural location in document")
    char_start: Optional[int] = Field(None, ge=0, description="Character start offset in original source")
    char_end: Optional[int] = Field(None, ge=0, description="Character end offset in original source")
