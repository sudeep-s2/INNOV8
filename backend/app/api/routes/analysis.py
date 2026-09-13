import asyncio
import logging
from typing import List, Optional, Union, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
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
from app.services.job_manager import get_job_manager, JobStatus
from app.validators.grounding import GroundingValidationError

logger = logging.getLogger(__name__)

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

class JobInitResponse(BaseModel):
    job_id: str
    status: str = JobStatus.PROCESSING

async def _run_analysis_job(job_id: str, source_text: str, chunks: List[SourceChunk]):
    """Background worker executing canonical analysis with Ollama Qwen3."""
    mgr = get_job_manager()
    ai_service = get_ai_service()
    try:
        logger.info(f"Starting background canonical analysis for job {job_id}")
        structured_model = await ai_service.analyze_source(source_text=source_text, chunks=chunks)
        mgr.set_completed(job_id, structured_model)
        logger.info(f"Successfully completed analysis for job {job_id}")
    except OllamaConnectionError as e:
        logger.error(f"Job {job_id} failed with connection error: {e}")
        mgr.set_failed(job_id, f"Ensure Ollama is running at configured base URL: {str(e)}")
    except OllamaTimeoutError as e:
        logger.error(f"Job {job_id} timed out: {e}")
        mgr.set_failed(job_id, f"Ollama model inference timed out: {str(e)}")
    except OllamaModelError as e:
        logger.error(f"Job {job_id} model error: {e}")
        mgr.set_failed(job_id, f"Ollama execution error: {str(e)}")
    except (AIServiceValidationError, GroundingValidationError) as e:
        logger.error(f"Job {job_id} grounding/validation error: {e}")
        mgr.set_failed(job_id, f"Canonical analysis failed validation/grounding: {str(e)}")
    except ValueError as e:
        logger.error(f"Job {job_id} value error: {e}")
        mgr.set_failed(job_id, str(e))
    except Exception as e:
        logger.exception(f"Job {job_id} unexpected error: {e}")
        mgr.set_failed(job_id, f"An unexpected error occurred during canonical analysis: {str(e)}")

@router.post(
    "/analyze",
    summary="Extract Source-Grounded Canonical Structured Content Model using Ollama Qwen3",
    status_code=status.HTTP_200_OK,
)
async def analyze_source_endpoint(
    request: AnalyzeRequest,
    sync: bool = Query(False, description="Run synchronously if True (default False for async job pattern)")
):
    """
    Parses source text/chunks and executes canonical analysis.
    By default, dispatches as an asynchronous background job and immediately returns { job_id, status: 'processing' }.
    """
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

    # If synchronous execution is explicitly requested (e.g. for direct legacy callers)
    if sync:
        ai_service = get_ai_service()
        try:
            structured_model = await ai_service.analyze_source(source_text=source_text, chunks=chunks)
            return structured_model
        except OllamaConnectionError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        except OllamaTimeoutError as e:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
        except OllamaModelError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama execution error: {str(e)}")
        except (AIServiceValidationError, GroundingValidationError) as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Canonical analysis failed validation/grounding: {str(e)}")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during canonical analysis: {str(e)}")

    # Asynchronous job pattern (standard)
    mgr = get_job_manager()
    job_id = mgr.create_job()
    asyncio.create_task(_run_analysis_job(job_id, source_text, chunks))

    return {
        "job_id": job_id,
        "status": JobStatus.PROCESSING
    }

@router.get(
    "/analyze/status/{job_id}",
    summary="Query status of an asynchronous analysis job",
    status_code=status.HTTP_200_OK,
)
async def get_analysis_status_endpoint(job_id: str):
    """
    Returns the current execution status of an analysis job:
    - while running: { "job_id": job_id, "status": "processing" }
    - when failed: { "job_id": job_id, "status": "failed", "error": "..." }
    - when complete: canonical analysis result including { "job_id": job_id, "status": "completed", "result": {...}, ... }
    """
    mgr = get_job_manager()
    job = mgr.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found or expired."
        )

    job_status = job["status"]

    if job_status == JobStatus.PROCESSING:
        return {
            "job_id": job_id,
            "status": JobStatus.PROCESSING
        }

    if job_status == JobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": JobStatus.FAILED,
            "error": job.get("error", "Unknown error occurred during analysis.")
        }

    # Completed status
    model: StructuredContentModel = job["result"]
    model_dict = model.model_dump() if hasattr(model, "model_dump") else dict(model)
    response_payload = {
        "job_id": job_id,
        "status": JobStatus.COMPLETED,
        "result": model_dict
    }
    # Spread model keys into response payload so client can access both .result and canonical fields directly
    response_payload.update(model_dict)
    return response_payload
