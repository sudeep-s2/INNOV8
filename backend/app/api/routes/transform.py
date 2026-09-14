import asyncio
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from app.models.outputs import (
    ExecutiveSummary,
    AdvisoryBrief,
    PublicCommunication,
    PresentationOutline
)
from app.models.transformation import (
    ExecutiveSummaryTransformRequest,
    AdvisoryBriefTransformRequest,
    PublicCommunicationTransformRequest,
    PresentationTransformRequest,
    MultiTransformRequest,
    MultiTransformResponse
)
from app.services.transformations.executive_summary import ExecutiveSummaryGenerator
from app.services.transformations.advisory_brief import AdvisoryBriefGenerator
from app.services.transformations.public_communication import PublicCommunicationGenerator
from app.services.transformations.presentation import PresentationGenerator
from app.services.transformations.orchestrator import TransformationOrchestrator
from app.services.job_manager import get_job_manager, JobStatus
from app.services.base import (
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError,
)
from app.validators.grounding import GroundingValidationError

logger = logging.getLogger(__name__)

router = APIRouter()
exec_generator = ExecutiveSummaryGenerator()
advisory_generator = AdvisoryBriefGenerator()
public_comm_generator = PublicCommunicationGenerator()
presentation_generator = PresentationGenerator()
orchestrator = TransformationOrchestrator()

async def _run_transform_job(job_id: str, request: MultiTransformRequest):
    """Background worker executing multi-output transformations."""
    mgr = get_job_manager()
    try:
        logger.info(f"Starting background multi-transformation for job {job_id}")
        response = await orchestrator.transform_multi(
            structured_model=request.structured_model,
            config=request.config,
            output_types=request.output_types
        )
        mgr.set_completed(job_id, response)
        logger.info(f"Successfully completed multi-transformation for job {job_id}")
    except Exception as e:
        logger.exception(f"Job {job_id} failed during multi-transformation: {e}")
        mgr.set_failed(job_id, f"Transformation orchestration failed: {str(e)}")

@router.post(
    "",
    summary="Multi-Output Orchestration Transformation",
    status_code=status.HTTP_200_OK
)
async def transform_multi_endpoint(
    request: MultiTransformRequest,
    sync: bool = Query(False, description="Run synchronously if True (default False for async job pattern)")
):
    """
    Transforms a single canonical StructuredContentModel into multiple purpose-specific artefacts.
    By default, executes asynchronously via background jobs to prevent Cloudflare tunnel timeouts.
    """
    if not request.structured_model or not request.structured_model.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid structured_model with topic and facts is required for transformation."
        )

    if not request.output_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one output_type must be selected."
        )

    if sync:
        try:
            response = await orchestrator.transform_multi(
                structured_model=request.structured_model,
                config=request.config,
                output_types=request.output_types
            )
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during multi-transformation: {str(e)}"
            )

    mgr = get_job_manager()
    job_id = mgr.create_job()
    asyncio.create_task(_run_transform_job(job_id, request))

    return {
        "job_id": job_id,
        "status": JobStatus.PROCESSING
    }

@router.get(
    "/status/{job_id}",
    summary="Query status of an asynchronous transformation job",
    status_code=status.HTTP_200_OK,
)
async def get_transform_status_endpoint(job_id: str):
    """
    Returns the current execution status of a transformation job:
    - while running: { "job_id": job_id, "status": "processing" }
    - when failed: { "job_id": job_id, "status": "failed", "error": "..." }
    - when complete: { "job_id": job_id, "status": "completed", "result": {...}, ... }
    """
    mgr = get_job_manager()
    job = mgr.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transformation job '{job_id}' not found or expired."
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
            "error": job.get("error", "Unknown error occurred during transformation.")
        }

    resp = job["result"]
    resp_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    response_payload = {
        "job_id": job_id,
        "status": JobStatus.COMPLETED,
        "result": resp_dict
    }
    response_payload.update(resp_dict)
    return response_payload

@router.post(
    "/executive-summary",
    response_model=ExecutiveSummary,
    summary="Transform Canonical Model into Executive Summary",
    status_code=status.HTTP_200_OK
)
async def transform_executive_summary_endpoint(request: ExecutiveSummaryTransformRequest):
    """Transforms a canonical StructuredContentModel into a validated, source-grounded ExecutiveSummary."""
    if not request.structured_model or not request.structured_model.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid structured_model with topic and facts is required for transformation."
        )

    try:
        executive_summary = await exec_generator.transform(
            structured_model=request.structured_model,
            config=request.config
        )
        return executive_summary
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
            detail=f"Executive summary transformation failed validation/grounding: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during executive summary generation: {str(e)}"
        )

@router.post(
    "/advisory-brief",
    response_model=AdvisoryBrief,
    summary="Transform Canonical Model into Advisory Brief",
    status_code=status.HTTP_200_OK
)
async def transform_advisory_brief_endpoint(request: AdvisoryBriefTransformRequest):
    """Transforms a canonical StructuredContentModel into a formal, source-grounded AdvisoryBrief."""
    if not request.structured_model or not request.structured_model.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid structured_model with topic and facts is required for transformation."
        )

    try:
        advisory_brief = await advisory_generator.transform(
            structured_model=request.structured_model,
            config=request.config
        )
        return advisory_brief
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
            detail=f"Advisory brief transformation failed validation/grounding: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during advisory brief generation: {str(e)}"
        )

@router.post(
    "/public-communication",
    response_model=PublicCommunication,
    summary="Transform Canonical Model into Public Communication",
    status_code=status.HTTP_200_OK
)
async def transform_public_communication_endpoint(request: PublicCommunicationTransformRequest):
    """Transforms a canonical StructuredContentModel into an accessible, source-grounded PublicCommunication release."""
    if not request.structured_model or not request.structured_model.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid structured_model with topic and facts is required for transformation."
        )

    try:
        public_comm = await public_comm_generator.transform(
            structured_model=request.structured_model,
            config=request.config
        )
        return public_comm
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
            detail=f"Public communication transformation failed validation/grounding: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during public communication generation: {str(e)}"
        )

@router.post(
    "/presentation",
    response_model=PresentationOutline,
    summary="Transform Canonical Model into Presentation Outline",
    status_code=status.HTTP_200_OK
)
async def transform_presentation_endpoint(request: PresentationTransformRequest):
    """Transforms a canonical StructuredContentModel into a slide-by-slide, source-grounded PresentationOutline."""
    if not request.structured_model or not request.structured_model.topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid structured_model with topic and facts is required for transformation."
        )

    try:
        presentation = await presentation_generator.transform(
            structured_model=request.structured_model,
            config=request.config
        )
        return presentation
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
            detail=f"Presentation transformation failed validation/grounding: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during presentation generation: {str(e)}"
        )
