import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.source import SourceChunk
from app.models.content_model import (
    StructuredContentModel,
    KeyFact,
    Entity,
    EventDate,
    MetricNumber,
    RiskImplication,
    RecommendationAction,
    ImportantStatement,
)
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.services.ollama_service import OllamaAIService
from app.services.base import AIServiceValidationError

client = TestClient(app)

SAMPLE_CHUNKS = [
    SourceChunk(chunk_id="chunk_1", text="APT-44 breached SCADA substation gateway.", page_number=1),
    SourceChunk(chunk_id="chunk_2", text="4.8 GB of telemetry was exfiltrated on 2026-08-10.", page_number=1),
    SourceChunk(chunk_id="chunk_3", text="Recommendation: Isolate TCP port 2404 immediately.", page_number=2),
]

# 1. GroundingValidator Unit Tests
def test_grounding_validator_valid_model():
    model = StructuredContentModel(
        topic="SCADA Cyber Incident",
        summary="Breach occurred at electrical substations.",
        key_facts=[
            KeyFact(fact_id="f1", statement="Gateway breached", source_chunk_ids=["chunk_1"]),
            KeyFact(fact_id="f2", statement="Data exfiltrated", source_chunk_ids=["chunk_2"])
        ],
        entities=[
            Entity(name="APT-44", category="threat_actor", source_chunk_ids=["chunk_1"])
        ],
        dates=[
            EventDate(event="Breach detected", date_or_time="2026-08-10", source_chunk_ids=["chunk_2"])
        ],
        metrics=[
            MetricNumber(metric="Exfiltrated Volume", value="4.8 GB", source_chunk_ids=["chunk_2"])
        ],
        risks=[
            RiskImplication(risk="Grid compromise", severity="Critical", source_chunk_ids=["chunk_1", "chunk_2"])
        ],
        recommendations=[
            RecommendationAction(action="Isolate port 2404", priority="Immediate", source_chunk_ids=["chunk_3"])
        ],
        important_statements=[
            ImportantStatement(statement="Immediate containment required", source_chunk_ids=["chunk_3"])
        ],
        source_chunks=SAMPLE_CHUNKS
    )
    is_valid, errors = GroundingValidator.validate_model_grounding(model)
    assert is_valid is True
    assert len(errors) == 0
    GroundingValidator.assert_grounding(model)

def test_grounding_validator_rejects_nonexistent_chunk_id():
    model = StructuredContentModel(
        topic="SCADA Incident",
        summary="Summary text",
        key_facts=[
            KeyFact(fact_id="f1", statement="Hallucinated fact", source_chunk_ids=["chunk_99"])
        ],
        source_chunks=SAMPLE_CHUNKS
    )
    is_valid, errors = GroundingValidator.validate_model_grounding(model)
    assert is_valid is False
    assert any("chunk_99" in err for err in errors)

    with pytest.raises(GroundingValidationError) as exc_info:
        GroundingValidator.assert_grounding(model)
    assert "chunk_99" in str(exc_info.value)

def test_grounding_validator_rejects_empty_chunks_collection():
    model = StructuredContentModel(
        topic="No Chunks",
        summary="Summary text",
        source_chunks=[]
    )
    is_valid, errors = GroundingValidator.validate_model_grounding(model)
    assert is_valid is False
    assert "zero source chunks" in errors[0]

# 2. AI Service Grounding & Retry Mock Tests
def create_mock_response(status_code: int, content_dict: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = content_dict
    mock_resp.text = json.dumps(content_dict)
    return mock_resp

@pytest.mark.asyncio
async def test_ai_service_parses_valid_grounded_chunks():
    service = OllamaAIService()
    grounded_output = {
        "topic": "SCADA Cyber Incident",
        "summary": "APT-44 attacked SCADA nodes.",
        "key_facts": [
            {"fact_id": "f1", "statement": "Gateway breached", "source_chunk_ids": ["chunk_1"]}
        ],
        "entities": [
            {"name": "APT-44", "category": "threat_actor", "source_chunk_ids": ["chunk_1"]}
        ],
        "dates": [],
        "metrics": [],
        "risks": [],
        "recommendations": [],
        "important_statements": []
    }
    mock_resp = create_mock_response(200, {"message": {"content": json.dumps(grounded_output)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        model = await service.analyze_source(
            source_text="Source text",
            chunks=SAMPLE_CHUNKS
        )
        assert model.topic == "SCADA Cyber Incident"
        assert len(model.source_chunks) == 3
        assert model.key_facts[0].source_chunk_ids == ["chunk_1"]
        assert model.entities[0].source_chunk_ids == ["chunk_1"]

@pytest.mark.asyncio
async def test_ai_service_corrective_retry_on_invalid_grounding():
    service = OllamaAIService()
    
    # 1st response has invalid chunk_99
    bad_output = {
        "topic": "SCADA Incident",
        "summary": "Summary",
        "key_facts": [{"fact_id": "f1", "statement": "Fact", "source_chunk_ids": ["chunk_99"]}],
        "entities": [], "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []
    }
    # 2nd response fixes it to chunk_1
    good_output = {
        "topic": "SCADA Incident",
        "summary": "Summary",
        "key_facts": [{"fact_id": "f1", "statement": "Fact", "source_chunk_ids": ["chunk_1"]}],
        "entities": [], "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []
    }

    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_output)}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(good_output)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        model = await service.analyze_source("Source text", chunks=SAMPLE_CHUNKS)
        assert model.key_facts[0].source_chunk_ids == ["chunk_1"]

@pytest.mark.asyncio
async def test_ai_service_fails_when_grounding_remains_invalid():
    service = OllamaAIService()
    bad_output = {
        "topic": "SCADA Incident",
        "summary": "Summary",
        "key_facts": [{"fact_id": "f1", "statement": "Fact", "source_chunk_ids": ["chunk_99"]}],
        "entities": [], "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []
    }
    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_output)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await service.analyze_source("Source text", chunks=SAMPLE_CHUNKS)

# 3. API Endpoint Tests
def test_api_canonical_analyze_with_source_text():
    mock_output = {
        "topic": "Power Grid Incident",
        "summary": "Incident telemetry summary.",
        "key_facts": [{"fact_id": "f1", "statement": "14 sub-stations compromised", "source_chunk_ids": ["chunk_1"]}],
        "entities": [{"name": "APT-44", "category": "threat_actor", "source_chunk_ids": ["chunk_1"]}],
        "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []
    }
    mock_resp = create_mock_response(200, {"message": {"content": json.dumps(mock_output)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = client.post(
            "/api/ai/analyze",
            json={"source_text": "CRITICAL TELEMETRY: 14 sub-stations compromised by threat actor APT-44."}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Power Grid Incident"
        assert len(data["source_chunks"]) >= 1
        assert data["key_facts"][0]["source_chunk_ids"] == ["chunk_1"]

def test_api_canonical_analyze_with_pre_ingested_chunks():
    mock_output = {
        "topic": "Pre-chunked Source Analysis",
        "summary": "Summary of pre-chunked input.",
        "key_facts": [{"fact_id": "f1", "statement": "Fact from chunk 2", "source_chunk_ids": ["chunk_2"]}],
        "entities": [], "dates": [], "metrics": [], "risks": [], "recommendations": [], "important_statements": []
    }
    mock_resp = create_mock_response(200, {"message": {"content": json.dumps(mock_output)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = client.post(
            "/api/ai/analyze",
            json={
                "chunks": [c.model_dump() for c in SAMPLE_CHUNKS]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Pre-chunked Source Analysis"
        assert len(data["source_chunks"]) == 3
        assert data["key_facts"][0]["source_chunk_ids"] == ["chunk_2"]

def test_api_canonical_analyze_rejects_empty_payload():
    response = client.post("/api/ai/analyze", json={})
    assert response.status_code == 400
