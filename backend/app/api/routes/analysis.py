from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.source import SourceChunk
from app.models.content_model import StructuredContentModel
from app.parsers.document_parser import DocumentParser, EmptyTextError
from app.services import (
    get_ai_service,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError,
)
from app.validators.grounding import GroundingValidationError

router = APIRouter()
doc_parser = DocumentParser()

class AnalyzeRequest(BaseModel):
    source_text: Optional[str] = Field(
        None,
        description="Authoritative source text to be parsed and analyzed into a StructuredContentModel"
    )
    chunks: Optional[List[SourceChunk]] = Field(
        None,
        description="Optional pre-segmented SourceChunk objects (e.g. from document ingestion)"
    )

@router.post(
    "/analyze",
    response_model=StructuredContentModel,
    summary="Extract Source-Grounded Canonical Structured Content Model using Ollama Qwen3",
    status_code=status.HTTP_200_OK,
)
async def analyze_source_endpoint(request: AnalyzeRequest):
    """Parses source text/chunks and executes single-pass canonical analysis with deterministic source grounding."""
    chunks: List[SourceChunk] = []
    source_text: str = ""

    if request.chunks and len(request.chunks) > 0:
        chunks = request.chunks
        source_text = request.source_text or "\n\n".join([c.text for c in chunks])
    elif request.source_text and len(request.source_text.strip()) >= 10:
        try:
            sanitized, parsed_chunks = doc_parser.parse_text(request.source_text)
            chunks = parsed_chunks
            source_text = sanitized
        except EmptyTextError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid source_text (minimum 10 characters) or non-empty chunks list is required."
        )

    ai_service = get_ai_service()

    try:
        structured_model = await ai_service.analyze_source(source_text=source_text, chunks=chunks)
        return structured_model
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except OllamaTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e)
        )
    except OllamaModelError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama execution error: {str(e)}"
        )
    except (AIServiceValidationError, GroundingValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Canonical analysis failed validation/grounding: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during canonical analysis: {str(e)}"
        )
