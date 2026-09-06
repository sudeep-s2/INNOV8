import io
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.parsers import (
    sanitize_text,
    SemanticChunker,
    TextParser,
    PdfParser,
    DocumentParser,
    EmptyTextError,
    EmptyPDFError,
    MalformedPDFError,
)
from app.models.source import SourceChunk
from app.models.ingest import IngestResponse
from app.services.ollama_service import OllamaAIService

client = TestClient(app)

def create_synthetic_pdf(text_pages: list[str]) -> bytes:
    """Constructs a minimal valid multi-page PDF binary stream containing the specified text pages."""
    objects = []
    # 1. Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    
    # 2. Pages object
    page_count = len(text_pages)
    kids_refs = " ".join([f"{3 + i*3} 0 R" for i in range(page_count)])
    objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids_refs}] /Count {page_count} >>\nendobj\n".encode())

    # Build page, font, content objects
    for i, page_text in enumerate(text_pages):
        page_obj_num = 3 + i * 3
        font_obj_num = page_obj_num + 1
        content_obj_num = page_obj_num + 2

        # Clean text for PDF literal string
        safe_text = page_text.replace("(", "\\(").replace(")", "\\)").replace("\n", " ")
        stream_content = f"BT\n/F1 12 Tf\n50 700 Td\n({safe_text}) Tj\nET\n".encode()

        objects.append(
            f"{page_obj_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> /Contents {content_obj_num} 0 R >>\nendobj\n".encode()
        )
        objects.append(
            f"{font_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode()
        )
        objects.append(
            f"{content_obj_num} 0 obj\n<< /Length {len(stream_content)} >>\nstream\n".encode() +
            stream_content + b"\nendstream\nendobj\n"
        )

    # Assemble PDF with basic header and trailer
    pdf_bytes = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf_bytes))
        pdf_bytes += obj

    xref_offset = len(pdf_bytes)
    total_objs = len(objects) + 1
    xref = f"xref\n0 {total_objs}\n0000000000 65535 f \n".encode()
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return pdf_bytes + xref + trailer

# 1. Sanitizer Tests
def test_sanitize_text_normalizes_line_endings_and_bom():
    raw = "\ufeffLine 1\r\n\r\nLine 2\rLine 3\n\n\n\nLine 4   with   spaces"
    sanitized = sanitize_text(raw)
    assert "\ufeff" not in sanitized
    assert "\r" not in sanitized
    assert "\n\n\n" not in sanitized
    assert "Line 4 with spaces" in sanitized

def test_sanitize_text_preserves_technical_identifiers():
    raw = "Vulnerability CVE-2026-38910 detected on 192.168.1.104:2404 on 2026-08-15. Exfiltrated 4.8 GB."
    sanitized = sanitize_text(raw)
    assert "CVE-2026-38910" in sanitized
    assert "192.168.1.104:2404" in sanitized
    assert "2026-08-15" in sanitized
    assert "4.8 GB" in sanitized

# 2. Chunker Tests
def test_semantic_chunker_deterministic_ids_and_offsets():
    chunker = SemanticChunker(max_chunk_size=300, min_chunk_size=50)
    text = (
        "SECTION 1: INCIDENT OVERVIEW\n\n"
        "APT-44 conducted malicious reconnaissance against four regional power load dispatch centers.\n\n"
        "SECTION 2: REMEDIATION\n\n"
        "All operators must immediately isolate TCP port 2404 and install emergency security hotfix KB-2026-08."
    )
    chunks, next_idx = chunker.chunk_text(text, page_number=1)
    assert len(chunks) >= 2
    assert chunks[0].chunk_id == "chunk_1"
    assert chunks[1].chunk_id == "chunk_2"
    assert next_idx == len(chunks) + 1

    for c in chunks:
        assert c.char_start is not None
        assert c.char_end is not None
        assert c.char_start < c.char_end
        assert c.page_number == 1

def test_semantic_chunker_handles_large_paragraphs():
    chunker = SemanticChunker(max_chunk_size=100, min_chunk_size=20)
    long_text = "First sentence of paragraph. Second sentence of paragraph. Third sentence of paragraph. Fourth sentence of paragraph."
    chunks, _ = chunker.chunk_text(long_text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) > 0

# 3. TextParser Tests
def test_text_parser_utf8_and_latin1():
    utf8_bytes = "Telemetry report with UTF-8 chars: ü, é, ₹1000".encode("utf-8")
    assert "₹1000" in TextParser.parse_bytes(utf8_bytes)

    latin1_bytes = "Sensor report with Latin-1: café".encode("latin-1")
    assert "café" in TextParser.parse_bytes(latin1_bytes)

def test_text_parser_rejects_empty():
    with pytest.raises(EmptyTextError):
        TextParser.parse_bytes(b"   \n\t  ")

# 4. PdfParser Tests
def test_pdf_parser_valid_multipage():
    pdf_bytes = create_synthetic_pdf([
        "Page 1: National Security Telemetry Briefing",
        "Page 2: APT-44 Threat Analysis and Mitigation Directives"
    ])
    pages = PdfParser.extract_pages(pdf_bytes)
    assert len(pages) == 2
    assert pages[0][0] == 1
    assert "Page 1" in pages[0][1]
    assert pages[1][0] == 2
    assert "APT-44" in pages[1][1]

def test_pdf_parser_rejects_empty_bytes():
    with pytest.raises(EmptyPDFError):
        PdfParser.extract_pages(b"")

def test_pdf_parser_rejects_malformed_bytes():
    with pytest.raises(MalformedPDFError):
        PdfParser.extract_pages(b"NOT_A_PDF_CORRUPT_BYTES")

# 5. DocumentParser Coordinator Tests
def test_document_parser_text_flow():
    parser = DocumentParser()
    sanitized, chunks = parser.parse_text("Sample intelligence dossier paragraph with at least 50 characters of content.")
    assert len(sanitized) > 0
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "chunk_1"

def test_document_parser_pdf_flow():
    parser = DocumentParser()
    pdf_bytes = create_synthetic_pdf([
        "SECTION 1: Cyber Threat Assessment.\n\nAPT-44 attacked SCADA nodes.",
        "SECTION 2: Recommended Remediation.\n\nDeploy patch KB-2026-08."
    ])
    sanitized, chunks = parser.parse_pdf_file(pdf_bytes, filename="threat_intel.pdf")
    assert len(chunks) >= 2
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2

# 6. API Route Tests (/api/source/ingest & /api/source/upload)
def test_api_ingest_pasted_text_success():
    payload = {
        "text": "CRITICAL TELEMETRY FINDINGS\n\nSensors identified unauthorized access targeting 14 sub-stations.",
        "title": "Grid Report"
    }
    response = client.post("/api/source/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "text"
    assert data["filename"] == "Grid Report"
    assert data["chunk_count"] >= 1
    assert len(data["chunks"]) == data["chunk_count"]
    assert data["chunks"][0]["chunk_id"] == "chunk_1"

def test_api_ingest_pasted_text_short_rejected():
    response = client.post("/api/source/ingest", json={"text": "short"})
    assert response.status_code == 422

def test_api_upload_txt_file_success():
    txt_content = b"SCADA INCIDENT REPORT\n\nAPT-44 breached gateway on 2026-08-10."
    files = {"file": ("incident_log.txt", txt_content, "text/plain")}
    response = client.post("/api/source/upload", files=files, data={"title": "Custom Incident Title"})
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "txt"
    assert data["filename"] == "Custom Incident Title"
    assert data["chunk_count"] >= 1

def test_api_upload_pdf_file_success():
    pdf_bytes = create_synthetic_pdf([
        "Page 1: Telemetry Data Overview",
        "Page 2: Mitigation Directive 2026"
    ])
    files = {"file": ("threat_report.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/source/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "pdf"
    assert data["filename"] == "threat_report.pdf"
    assert data["chunk_count"] >= 2
    assert data["chunks"][0]["page_number"] == 1

def test_api_upload_unsupported_file_extension():
    files = {"file": ("malicious.exe", b"binary content", "application/octet-stream")}
    response = client.post("/api/source/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_api_upload_empty_file():
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = client.post("/api/source/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

# 7. Integration: Ingestion chunks feeding AIService
@pytest.mark.asyncio
async def test_ingested_chunks_compatible_with_ai_service():
    """Verify that chunks produced by DocumentParser pass cleanly into AIService."""
    parser = DocumentParser()
    _, chunks = parser.parse_text("SCADA telemetry report text for testing AI service integration.")
    
    service = OllamaAIService()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "role": "assistant",
            "content": '{"topic": "SCADA Telemetry", "summary": "Summary text", "key_facts": [], "entities": [], "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []}'
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await service.analyze_source("SCADA telemetry report text.", chunks=chunks)
        assert result.topic == "SCADA Telemetry"
        assert len(result.source_chunks) == len(chunks)
        assert result.source_chunks[0].chunk_id == "chunk_1"
