import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.models.content_model import StructuredContentModel
from app.services.base import (
    OllamaConnectionError,
    OllamaTimeoutError,
    AIServiceError,
)
from app.services.groq_service import GroqAIService
from app.services.fallback_service import FallbackAIService

client = TestClient(app)

SAMPLE_GROQ_JSON = {
    "topic": "Power Grid Cyber Intrusion",
    "summary": "APT-44 breached SCADA network via CVE-2026-38910.",
    "key_facts": [
        {
            "fact_id": "fact_1",
            "statement": "SCADA controllers compromised across 4 centers.",
            "metric_or_date": "4",
            "source_chunk_ids": ["chunk_1"]
        }
    ],
    "entities": [
        {"name": "APT-44", "category": "threat_actor", "source_chunk_ids": ["chunk_1"]}
    ],
    "dates": [
        {"event": "Infiltration", "date_or_time": "2026-08-10", "source_chunk_ids": ["chunk_1"]}
    ],
    "metrics": [
        {"metric": "Exfiltrated", "value": "4.8 GB", "source_chunk_ids": ["chunk_1"]}
    ],
    "risks": [
        {"risk": "Grid failure", "source_chunk_ids": ["chunk_1"]}
    ],
    "recommendations": [
        {"action": "Apply KB-2026-08", "priority": "Immediate", "source_chunk_ids": ["chunk_1"]}
    ],
    "important_statements": [
        {"statement": "Substation telemetry disconnected", "source_chunk_ids": ["chunk_1"]}
    ]
}

def create_mock_groq_response(status_code: int, content_dict: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content_dict)
                }
            }
        ]
    }
    mock_resp.text = json.dumps(mock_resp.json.return_value)
    return mock_resp

@pytest.mark.asyncio
async def test_groq_service_success():
    """Verify GroqAIService parses structured output into StructuredContentModel."""
    service = GroqAIService(api_key="mock_key_123")
    mock_resp = create_mock_groq_response(200, SAMPLE_GROQ_JSON)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await service.analyze_source("Sample telemetry intelligence source text.")
        assert isinstance(result, StructuredContentModel)
        assert result.topic == "Power Grid Cyber Intrusion"
        assert len(result.key_facts) == 1

@pytest.mark.asyncio
async def test_groq_service_unconfigured():
    """Verify GroqAIService raises AIServiceError when api_key is missing."""
    service = GroqAIService(api_key="")
    with pytest.raises(AIServiceError):
        await service._call_api("prompt")

@pytest.mark.asyncio
async def test_fallback_ai_service_uses_primary_when_healthy():
    """Verify FallbackAIService returns primary result when primary is healthy."""
    primary_mock = AsyncMock()
    primary_mock.analyze_source.return_value = StructuredContentModel(**SAMPLE_GROQ_JSON)

    fallback_mock = AsyncMock()
    fallback_mock.is_available = MagicMock(return_value=True)

    service = FallbackAIService(primary=primary_mock, fallback=fallback_mock)
    res = await service.analyze_source("Sample source text.")

    assert res.topic == "Power Grid Cyber Intrusion"
    primary_mock.analyze_source.assert_awaited_once()
    fallback_mock.analyze_source.assert_not_awaited()

@pytest.mark.asyncio
async def test_fallback_ai_service_switches_to_groq_on_ollama_failure():
    """Verify FallbackAIService transparently routes to Groq when Ollama connection fails."""
    primary_mock = AsyncMock()
    primary_mock.analyze_source.side_effect = OllamaConnectionError("Ollama connection refused")

    fallback_mock = AsyncMock()
    fallback_mock.is_available = MagicMock(return_value=True)
    fallback_mock.analyze_source.return_value = StructuredContentModel(**SAMPLE_GROQ_JSON)

    service = FallbackAIService(primary=primary_mock, fallback=fallback_mock)
    res = await service.analyze_source("Sample source text.")

    assert res.topic == "Power Grid Cyber Intrusion"
    primary_mock.analyze_source.assert_awaited_once()
    fallback_mock.analyze_source.assert_awaited_once()

@pytest.mark.asyncio
async def test_fallback_ai_service_switches_to_groq_on_ollama_timeout():
    """Verify FallbackAIService transparently routes to Groq when Ollama inference times out."""
    primary_mock = AsyncMock()
    primary_mock.analyze_source.side_effect = OllamaTimeoutError("Ollama inference timed out after 180s")

    fallback_mock = AsyncMock()
    fallback_mock.is_available = MagicMock(return_value=True)
    fallback_mock.analyze_source.return_value = StructuredContentModel(**SAMPLE_GROQ_JSON)

    service = FallbackAIService(primary=primary_mock, fallback=fallback_mock)
    res = await service.analyze_source("Sample source text.")

    assert res.topic == "Power Grid Cyber Intrusion"
    fallback_mock.analyze_source.assert_awaited_once()

def test_readiness_probe_endpoint():
    """Verify GET /api/ready returns operational readiness status."""
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert "ollama_online" in data
    assert "fallback_configured" in data
    assert data["service"] == "info2impact"
