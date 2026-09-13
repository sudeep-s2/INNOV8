import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_service import OllamaAIService
from app.services.base import (
    OllamaConnectionError,
    OllamaTimeoutError,
    AIServiceValidationError,
)
from app.models.content_model import StructuredContentModel

client = TestClient(app)

SAMPLE_VALID_JSON = {
    "topic": "Power Grid Cyber Intrusion",
    "summary": "APT-44 exploited an unpatched SCADA protocol vulnerability across 14 regional nodes.",
    "key_facts": [
        {
            "fact_id": "fact_1",
            "statement": "14 regional dispatch centers experienced telemetry drops",
            "metric_or_date": "14",
            "source_chunk_ids": ["chunk_1"]
        }
    ],
    "entities": [
        {"name": "APT-44", "category": "threat_actor", "source_chunk_ids": ["chunk_1"]}
    ],
    "dates": [
        {"event": "Initial breach detection", "date_or_time": "2026-08-10", "source_chunk_ids": ["chunk_1"]}
    ],
    "metrics": [
        {"metric": "Data Exfiltrated", "value": "4.8 GB", "context": "C2 network transfer", "source_chunk_ids": ["chunk_1"]}
    ],
    "risks": [
        {"risk": "Grid instability during peak load", "severity": "Critical", "mitigation": "Data diodes", "source_chunk_ids": ["chunk_1"]}
    ],
    "recommendations": [
        {"action": "Apply KB-2026-08-HOTFIX", "priority": "Immediate", "source_chunk_ids": ["chunk_1"]}
    ],
    "important_statements": [
        {"statement": "Mechanical interlocks prevented blackout", "source_chunk_ids": ["chunk_1"]}
    ]
}

def create_mock_httpx_response(status_code: int, content_dict: dict) -> MagicMock:
    """Helper creating a synchronous httpx-like Response mock."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = content_dict
    mock_resp.text = json.dumps(content_dict)
    return mock_resp

@pytest.mark.asyncio
async def test_ollama_service_valid_json_parsing():
    """Verify OllamaAIService successfully parses valid JSON into a StructuredContentModel."""
    service = OllamaAIService()

    mock_resp = create_mock_httpx_response(200, {
        "message": {
            "role": "assistant",
            "content": json.dumps(SAMPLE_VALID_JSON)
        }
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await service.analyze_source("Sample telemetry source text describing SCADA intrusion.")
        assert isinstance(result, StructuredContentModel)
        assert result.topic == "Power Grid Cyber Intrusion"
        assert len(result.key_facts) == 1
        assert result.key_facts[0].statement.startswith("14 regional")
        assert len(result.source_chunks) >= 1

@pytest.mark.asyncio
async def test_ollama_service_strips_markdown_codeblocks():
    """Verify OllamaAIService cleanly handles JSON wrapped in markdown code blocks."""
    service = OllamaAIService()

    wrapped_content = f"```json\n{json.dumps(SAMPLE_VALID_JSON)}\n```"
    mock_resp = create_mock_httpx_response(200, {
        "message": {
            "role": "assistant",
            "content": wrapped_content
        }
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await service.analyze_source("Sample telemetry source text.")
        assert result.topic == "Power Grid Cyber Intrusion"

@pytest.mark.asyncio
async def test_ollama_service_corrective_retry_on_invalid_json():
    """Verify OllamaAIService retries once when initial output is invalid JSON, and succeeds on second attempt."""
    service = OllamaAIService()

    bad_resp = create_mock_httpx_response(200, {"message": {"content": "INVALID_NOT_JSON"}})
    good_resp = create_mock_httpx_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await service.analyze_source("Source text requiring corrective retry.")
        assert result.topic == "Power Grid Cyber Intrusion"

@pytest.mark.asyncio
async def test_ollama_service_fails_after_failed_retry():
    """Verify AIServiceValidationError is raised if even corrective retry fails."""
    service = OllamaAIService()

    bad_resp = create_mock_httpx_response(200, {"message": {"content": "MALFORMED_OUTPUT"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await service.analyze_source("Source text with permanent malformed output.")

@pytest.mark.asyncio
async def test_ollama_service_connection_error():
    """Verify OllamaConnectionError is raised when httpx cannot connect to Ollama."""
    service = OllamaAIService()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        with pytest.raises(OllamaConnectionError):
            await service.analyze_source("Source text for connection test.")

@pytest.mark.asyncio
async def test_ollama_service_timeout_error():
    """Verify OllamaTimeoutError is raised when Ollama request times out."""
    service = OllamaAIService()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Read timeout")
        with pytest.raises(OllamaTimeoutError):
            await service.analyze_source("Source text for timeout test.")

@pytest.mark.asyncio
async def test_ollama_service_rejects_empty_source():
    """Verify empty or whitespace-only source text is immediately rejected without network calls."""
    service = OllamaAIService()
    with pytest.raises(ValueError):
        await service.analyze_source("   ")

# API Endpoint Tests
def test_api_analyze_endpoint_success():
    """Test POST /api/ai/analyze returns 200 and dispatches background job."""
    mock_resp = create_mock_httpx_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = client.post(
            "/api/ai/analyze",
            json={"source_text": "Sample valid intelligence briefing source text with more than 10 characters."}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"

        # Also verify sync fallback if requested
        sync_response = client.post(
            "/api/ai/analyze?sync=true",
            json={"source_text": "Sample valid intelligence briefing source text with more than 10 characters."}
        )
        assert sync_response.status_code == 200
        assert sync_response.json()["topic"] == "Power Grid Cyber Intrusion"
        assert len(sync_response.json()["key_facts"]) == 1

def test_api_analyze_endpoint_empty_input_validation():
    """Test POST /api/ai/analyze returns 400 or 422 for text shorter than min_length constraint."""
    response = client.post("/api/ai/analyze", json={"source_text": "short"})
    assert response.status_code in [400, 422]

def test_api_analyze_endpoint_connection_error_handling():
    """Test POST /api/ai/analyze returns HTTP 503 when sync is used and Ollama server is unreachable."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        response = client.post(
            "/api/ai/analyze?sync=true",
            json={"source_text": "Sample text for testing offline Ollama service response."}
        )
        assert response.status_code == 503
        assert "Ensure Ollama is running" in response.json()["detail"]
