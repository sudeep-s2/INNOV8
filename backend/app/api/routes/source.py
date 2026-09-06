from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.models.ingest import TextIngestRequest, IngestResponse
from app.parsers import (
    DocumentParser,
    EmptyTextError,
    EmptyPDFError,
    EncryptedPDFError,
    MalformedPDFError,
    TextParserError
)

router = APIRouter()
parser = DocumentParser()

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest and Segment Pasted Text",
    status_code=status.HTTP_200_OK
)
async def ingest_text_endpoint(request: TextIngestRequest):
    """Sanitizes raw text and segments it into addressable SourceChunk objects."""
    cleaned_text = request.text.strip()
    if len(cleaned_text) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source text must contain at least 10 non-whitespace characters."
        )

    try:
        sanitized_text, chunks = parser.parse_text(cleaned_text)
        word_count = len(sanitized_text.split())
        return IngestResponse(
            source_type="text",
            filename=request.title or "Pasted Text",
            character_count=len(sanitized_text),
            word_count=word_count,
            chunk_count=len(chunks),
            chunks=chunks
        )
    except EmptyTextError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during text ingestion: {str(e)}"
        )

@router.post(
    "/upload",
    response_model=IngestResponse,
    summary="Upload and Ingest TXT or PDF Document",
    status_code=status.HTTP_200_OK
)
async def upload_document_endpoint(
    file: UploadFile = File(..., description="TXT or PDF document to upload"),
    title: Optional[str] = Form(None, description="Optional custom document title")
):
    """Uploads a .txt or .pdf document, sanitizes content, and segments it into SourceChunk objects."""
    filename = file.filename or "uploaded_document"
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext not in ["txt", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Only .txt and .pdf documents are supported."
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}"
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    doc_title = title or filename

    try:
        if ext == "txt":
            sanitized_text, chunks = parser.parse_txt_file(file_bytes, filename=doc_title)
            source_type = "txt"
        else:  # pdf
            sanitized_text, chunks = parser.parse_pdf_file(file_bytes, filename=doc_title)
            source_type = "pdf"

        word_count = len(sanitized_text.split())
        return IngestResponse(
            source_type=source_type,
            filename=doc_title,
            character_count=len(sanitized_text),
            word_count=word_count,
            chunk_count=len(chunks),
            chunks=chunks
        )
    except (EmptyTextError, EmptyPDFError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EncryptedPDFError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except (MalformedPDFError, TextParserError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error processing document '{filename}': {str(e)}"
        )
