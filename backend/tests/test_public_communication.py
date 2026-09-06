import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
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
from app.models.transformation import (
    TransformationConfig,
    PublicCommunicationTransformRequest,
    Audience,
    Tone,
    DetailLevel,
    Objective,
    Language,
)
from app.models.outputs import PublicCommunication
from app.services.transformations.public_communication import PublicCommunicationGenerator
from app.services.base import (
    AIServiceValidationError,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from app.prompts.public_communication import build_public_communication_prompt

client = TestClient(app)

SAMPLE_STRUCTURED_MODEL = StructuredContentModel(
    topic="National SCADA Grid Cyber Intrusion",
    summary="Sensors detected unauthorized reconnaissance activity targeting 4 regional load dispatch centers by threat group APT-44.",
    key_facts=[
        KeyFact(fact_id="fact_1", statement="4 regional load dispatch centers targeted", metric_or_date="4", source_chunk_ids=["chunk_1"]),
        KeyFact(fact_id="fact_2", statement="Zero-day CVE-2026-38910 exploited", metric_or_date="CVE-2026-38910", source_chunk_ids=["chunk_1"]),
    ],
    entities=[
        Entity(name="APT-44", category="threat_actor", source_chunk_ids=["chunk_1"]),
        Entity(name="SCADA Gateway", category="system", source_chunk_ids=["chunk_1"]),
    ],
    dates=[
        EventDate(event="Breach detected", date_or_time="2026-08-10", source_chunk_ids=["chunk_1"])
    ],
    metrics=[
        MetricNumber(metric="Exfiltrated Data", value="4.8 GB", source_chunk_ids=["chunk_1"])
    ],
    risks=[
        RiskImplication(risk="Potential grid desynchronization", severity="Critical", source_chunk_ids=["chunk_1"])
    ],
    recommendations=[
        RecommendationAction(action="Isolate SCADA IEC-104 ports immediately", priority="Immediate", source_chunk_ids=["chunk_2"])
    ],
    important_statements=[
        ImportantStatement(statement="Emergency containment protocols initiated", source_chunk_ids=["chunk_2"])
    ],
    source_chunks=[
        SourceChunk(chunk_id="chunk_1", text="Sensors detected unauthorized reconnaissance by APT-44 exploiting CVE-2026-38910. 4.8 GB exfiltrated on 2026-08-10.", page_number=1),
        SourceChunk(chunk_id="chunk_2", text="Remediation: Isolate SCADA IEC-104 ports immediately.", page_number=2),
    ]
)

SAMPLE_VALID_PUBLIC_COMM_JSON = {
    "headline": "Power Grid Security Update: Continuous Monitoring and Precautionary Safeguards in Place",
    "opening": "National grid authorities have detected and contained unauthorized digital probing attempts against regional management centers.",
    "core_message": "Electrical power supply remains completely stable, and immediate protective measures have been deployed to ensure uninterrupted service across all regions.",
    "explanation": "Security monitoring systems identified suspicious network activity targeting communication gateways. Specialist defense teams acted swiftly to isolate the targeted access points and apply system updates.",
    "public_guidance": "No public action is required. Power grids continue normal operation under enhanced 24/7 technical monitoring.",
    "source_references": [
        {
            "claim": "Unauthorized digital probing attempts detected against regional management centers",
            "source_chunk_id": "chunk_1",
            "source_snippet": "Sensors detected unauthorized reconnaissance by APT-44"
        },
        {
            "claim": "Immediate protective measures deployed to isolate targeted access points",
            "source_chunk_id": "chunk_2",
            "source_snippet": "Remediation: Isolate SCADA IEC-104 ports immediately."
        }
    ]
}

def create_mock_response(status_code: int, content_dict: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = content_dict
    mock_resp.text = json.dumps(content_dict)
    return mock_resp

# 1. Prompt Tests
def test_build_public_communication_prompt_includes_config_and_canonical_data():
    config = TransformationConfig(
        audience=Audience.general_public,
        tone=Tone.informative,
        detail_level=DetailLevel.brief,
        objective=Objective.communicate,
        language=Language.english
    )
    prompt = build_public_communication_prompt(SAMPLE_STRUCTURED_MODEL, config)
    assert "Target Audience: general_public" in prompt
    assert "Tone: informative" in prompt
    assert "National SCADA Grid Cyber Intrusion" in prompt
    assert "chunk_1" in prompt
    assert "chunk_2" in prompt

# 2. Generator Unit Tests
@pytest.mark.asyncio
async def test_public_communication_generator_success():
    generator = PublicCommunicationGenerator()
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_PUBLIC_COMM_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig(audience=Audience.general_public, tone=Tone.informative)
        )
        assert isinstance(result, PublicCommunication)
        assert result.headline.startswith("Power Grid Security Update")
        assert len(result.core_message) > 10
        assert len(result.source_references) == 2
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_public_communication_generator_corrective_retry_on_malformed_json():
    generator = PublicCommunicationGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "MALFORMED_NON_JSON"}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_PUBLIC_COMM_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, PublicCommunication)
        assert result.headline == SAMPLE_VALID_PUBLIC_COMM_JSON["headline"]

@pytest.mark.asyncio
async def test_public_communication_generator_corrective_retry_on_invalid_chunk_citation():
    generator = PublicCommunicationGenerator()
    bad_json = dict(SAMPLE_VALID_PUBLIC_COMM_JSON)
    bad_json["source_references"] = [
        {"claim": "Invalid claim", "source_chunk_id": "chunk_99", "source_snippet": "bad"}
    ]
    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_json)}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_PUBLIC_COMM_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, PublicCommunication)
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_public_communication_generator_fails_after_failed_retry():
    generator = PublicCommunicationGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "INVALID_OUTPUT_TWICE"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

@pytest.mark.asyncio
async def test_public_communication_generator_handles_ollama_connection_error():
    generator = PublicCommunicationGenerator()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(OllamaConnectionError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

# 3. API Endpoint Tests (POST /api/transform/public-communication)
def test_api_transform_public_communication_success():
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_PUBLIC_COMM_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {
                "audience": "general_public",
                "tone": "informative",
                "detail_level": "brief",
                "objective": "communicate",
                "language": "English"
            }
        }
        response = client.post("/api/transform/public-communication", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["headline"] == SAMPLE_VALID_PUBLIC_COMM_JSON["headline"]
        assert "power supply remains completely stable" in data["core_message"].lower()
        assert len(data["source_references"]) == 2
        assert data["source_references"][0]["source_chunk_id"] == "chunk_1"

def test_api_transform_public_communication_rejects_missing_model():
    response = client.post("/api/transform/public-communication", json={})
    assert response.status_code == 422

def test_api_transform_public_communication_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {"audience": "general_public", "tone": "informative"}
        }
        response = client.post("/api/transform/public-communication", json=payload)
        assert response.status_code == 503
        assert "Ensure Ollama is running" in response.json()["detail"]
