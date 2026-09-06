import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException, status
from app.config import settings
from app.models.schemas import (
    IngestTextRequest, IngestResponse, SourceChunk,
    StructuredContentModel, TransformationConfig, TransformRequest,
    TransformResponse, SingleOutputResponse, RegenerateRequest,
    SampleDocument, OutputType
)
from app.parsers.document_parser import DocumentParser
from app.services.ai_service import AIService
from app.services.sample_data import get_sample_documents, get_sample_by_id
from app.validators.output_validator import OutputValidator

router = APIRouter()

def get_api_key_from_header_or_env(header_key: Optional[str]) -> Optional[str]:
    return header_key or settings.GEMINI_API_KEY

# 1. Health & Status
@router.get("/health", summary="Service Health & Configuration Status")
async def health_check(x_gemini_api_key: Optional[str] = Header(None)):
    active_key = get_api_key_from_header_or_env(x_gemini_api_key)
    has_api_key = bool(active_key)
    masked_key = f"{active_key[:4]}...{active_key[-4:]}" if (has_api_key and len(active_key) > 8) else None
    
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "organization": settings.ORGANIZATION,
        "version": settings.VERSION,
        "has_api_key": has_api_key,
        "masked_key": masked_key,
        "model": settings.DEFAULT_GEMINI_MODEL
    }

# 2. Sample Documents for Instant Demo
@router.get("/sample-documents", response_model=List[SampleDocument], summary="Get Preloaded Sample Reports for Demo")
async def list_sample_documents():
    return get_sample_documents()

# 3. Source Ingestion - Plain Text
@router.post("/source/text", response_model=IngestResponse, summary="Ingest Plain Text & Generate Grounding Chunks")
async def ingest_plain_text(request: IngestTextRequest):
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source text cannot be empty (minimum 10 characters required)."
        )
    
    if len(request.text) > settings.MAX_SOURCE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source text exceeds maximum allowed size of {settings.MAX_SOURCE_LENGTH} characters."
        )

    cleaned_text, chunks = DocumentParser.parse_plain_text(request.text, default_title=request.title or "Source Text")
    
    words = len(cleaned_text.split())
    source_id = f"doc_{uuid.uuid4().hex[:8]}"

    return IngestResponse(
        source_id=source_id,
        title=request.title or "Source Text",
        total_characters=len(cleaned_text),
        total_words=words,
        chunks=chunks,
        raw_text=cleaned_text
    )

# 4. Source Ingestion - File Upload (TXT & PDF)
@router.post("/source/upload", response_model=IngestResponse, summary="Upload & Parse Document (TXT / PDF)")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format in V1. Please upload a .txt or .pdf document."
        )

    content_bytes = await file.read()
    if len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    doc_title = title or file.filename

    try:
        if filename_lower.endswith(".pdf"):
            cleaned_text, chunks = DocumentParser.parse_pdf_bytes(content_bytes, doc_title)
        else:
            cleaned_text, chunks = DocumentParser.parse_txt_bytes(content_bytes, doc_title)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Document parsing error: {str(e)}")

    words = len(cleaned_text.split())
    source_id = f"doc_{uuid.uuid4().hex[:8]}"

    return IngestResponse(
        source_id=source_id,
        title=doc_title,
        total_characters=len(cleaned_text),
        total_words=words,
        chunks=chunks,
        raw_text=cleaned_text
    )

# 5. Core Analysis Endpoint (Single Pass)
@router.post("/analyze", response_model=StructuredContentModel, summary="Generate Shared Structured Intermediate Model")
async def analyze_source(
    request: IngestTextRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    api_key = get_api_key_from_header_or_env(x_gemini_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY or provide X-Gemini-API-Key header."
        )

    cleaned_text, chunks = DocumentParser.parse_plain_text(request.text, default_title=request.title or "Source Document")
    
    ai_service = AIService(api_key=api_key)
    try:
        structured_model = ai_service.analyze_source(cleaned_text, chunks, api_key=api_key)
        return structured_model
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Source analysis failed: {str(e)}")

# 6. Multi-Artefact Transformation Pipeline
@router.post("/transform", response_model=TransformResponse, summary="Transform Source into Multiple Purpose-Specific Artefacts")
async def transform_content(
    request: TransformRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    start_time = time.time()
    api_key = get_api_key_from_header_or_env(x_gemini_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY in backend/.env or configure it via the UI settings."
        )

    ai_service = AIService(api_key=api_key)

    # Step 1: Ingest & Parse Chunks if not supplied
    if not request.chunks and request.source_text:
        _, chunks = DocumentParser.parse_plain_text(request.source_text, default_title="Source Text")
    elif request.chunks:
        chunks = request.chunks
    else:
        raise HTTPException(status_code=400, detail="Either source_text or chunks must be provided.")

    # Step 2: Content Analysis -> Shared Structured Content Model (Run once if not already provided)
    if request.structured_model:
        structured_model = request.structured_model
    else:
        full_text = request.source_text or "\n\n".join([c.content for c in chunks])
        try:
            structured_model = ai_service.analyze_source(full_text, chunks, api_key=api_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis pipeline stage failed: {str(e)}")

    # Step 3: Multi-Artefact Transformations from Shared Model
    outputs = {}
    for out_type in request.output_types:
        try:
            data, val_result = ai_service.generate_single_artefact(
                output_type=out_type,
                structured_model=structured_model,
                config=request.config,
                api_key=api_key
            )
            
            raw_markdown = OutputValidator.format_as_markdown(out_type, data)
            grounding = data.get("source_grounding", [])
            title = data.get("title") or data.get("presentation_title") or out_type.replace("_", " ").title()

            outputs[out_type] = SingleOutputResponse(
                output_type=out_type,
                title=title,
                raw_markdown=raw_markdown,
                structured_data=data,
                source_grounding=grounding,
                validation=val_result
            )
        except Exception as e:
            # Report graceful error for individual failure without crashing entire batch
            outputs[out_type] = SingleOutputResponse(
                output_type=out_type,
                title=f"Error generating {out_type}",
                raw_markdown=f"Transformation error: {str(e)}",
                structured_data={"error": str(e)},
                source_grounding=[],
                validation={"is_valid": False, "score": 0.0, "issues": [str(e)], "retried": False}
            )

    execution_time_ms = int((time.time() - start_time) * 1000)
    source_id = f"tf_{uuid.uuid4().hex[:8]}"

    return TransformResponse(
        source_id=source_id,
        structured_model=structured_model,
        outputs=outputs,
        execution_time_ms=execution_time_ms,
        metadata={
            "output_count": len(outputs),
            "audience": request.config.target_audience,
            "tone": request.config.tone,
            "detail": request.config.level_of_detail
        }
    )

# 7. Single Artefact Regeneration
@router.post("/transform/{output_type}/regenerate", response_model=SingleOutputResponse, summary="Regenerate a Single Artefact with Modified Controls")
async def regenerate_single_output(
    output_type: OutputType,
    request: RegenerateRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    api_key = get_api_key_from_header_or_env(x_gemini_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY in backend/.env or configure it via the UI settings."
        )

    ai_service = AIService(api_key=api_key)

    try:
        data, val_result = ai_service.generate_single_artefact(
            output_type=output_type,
            structured_model=request.structured_model,
            config=request.config,
            api_key=api_key
        )
        
        raw_markdown = OutputValidator.format_as_markdown(output_type, data)
        grounding = data.get("source_grounding", [])
        title = data.get("title") or data.get("presentation_title") or output_type.replace("_", " ").title()

        return SingleOutputResponse(
            output_type=output_type,
            title=title,
            raw_markdown=raw_markdown,
            structured_data=data,
            source_grounding=grounding,
            validation=val_result
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate {output_type}: {str(e)}"
        )
