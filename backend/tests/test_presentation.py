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
    PresentationTransformRequest,
    Audience,
    Tone,
    DetailLevel,
    Objective,
    Language,
)
from app.models.outputs import PresentationOutline
from app.services.transformations.presentation import PresentationGenerator
from app.services.base import (
    AIServiceValidationError,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from app.prompts.presentation import build_presentation_prompt

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

SAMPLE_VALID_PRESENTATION_JSON = {
    "presentation_title": "Executive Briefing: SCADA Cyber Defense & Incident Response",
    "slides": [
        {
            "slide_number": 1,
            "title": "Incident Background & Scope",
            "key_points": [
                "Sensors detected reconnaissance across 4 regional load dispatch centers.",
                "Threat group APT-44 identified as primary threat actor."
            ],
            "data_highlights": "4 dispatch centers targeted",
            "speaker_notes": "Welcome leadership. Today we review the recent telemetry intrusion on regional gateways.",
            "source_references": [
                {
                    "claim": "4 regional load dispatch centers targeted",
                    "source_chunk_id": "chunk_1",
                    "source_snippet": "Sensors detected unauthorized reconnaissance activity"
                }
            ]
        },
        {
            "slide_number": 2,
            "title": "Technical Impact & Exfiltration",
            "key_points": [
                "Zero-day exploit CVE-2026-38910 leveraged.",
                "4.8 GB of routing tables exfiltrated on 2026-08-10."
            ],
            "data_highlights": "4.8 GB data exfiltrated",
            "speaker_notes": "The adversary leveraged a zero-day vulnerability to pull routing configurations.",
            "source_references": [
                {
                    "claim": "4.8 GB data exfiltrated",
                    "source_chunk_id": "chunk_1",
                    "source_snippet": "4.8 GB exfiltrated on 2026-08-10"
                }
            ]
        }
    ],
    "source_references": [
        {
            "claim": "Comprehensive SCADA Incident telemetry",
            "source_chunk_id": "chunk_1",
            "source_snippet": "Sensors detected unauthorized reconnaissance"
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
def test_build_presentation_prompt_includes_config_and_canonical_data():
    config = TransformationConfig(
        audience=Audience.executive,
        tone=Tone.formal,
        detail_level=DetailLevel.standard,
        objective=Objective.brief,
        language=Language.english
    )
    prompt = build_presentation_prompt(SAMPLE_STRUCTURED_MODEL, config)
    assert "Target Audience: executive" in prompt
    assert "Tone: formal" in prompt
    assert "National SCADA Grid Cyber Intrusion" in prompt
    assert "chunk_1" in prompt
    assert "chunk_2" in prompt

# 2. Generator Unit Tests
@pytest.mark.asyncio
async def test_presentation_generator_success():
    generator = PresentationGenerator()
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_PRESENTATION_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, PresentationOutline)
        assert result.presentation_title.startswith("Executive Briefing")
        assert len(result.slides) == 2
        assert result.slides[0].slide_number == 1
        assert result.slides[0].source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_presentation_generator_corrective_retry_on_malformed_json():
    generator = PresentationGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "MALFORMED_NON_JSON"}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_PRESENTATION_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, PresentationOutline)
        assert result.presentation_title == SAMPLE_VALID_PRESENTATION_JSON["presentation_title"]

@pytest.mark.asyncio
async def test_presentation_generator_corrective_retry_on_invalid_chunk_citation():
    generator = PresentationGenerator()
    bad_json = dict(SAMPLE_VALID_PRESENTATION_JSON)
    bad_json["source_references"] = [
        {"claim": "Invalid claim", "source_chunk_id": "chunk_99", "source_snippet": "bad"}
    ]
    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_json)}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_PRESENTATION_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, PresentationOutline)
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_presentation_generator_fails_after_failed_retry():
    generator = PresentationGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "INVALID_OUTPUT"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

@pytest.mark.asyncio
async def test_presentation_generator_handles_ollama_connection_error():
    generator = PresentationGenerator()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(OllamaConnectionError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

# 3. API Endpoint Tests (POST /api/transform/presentation)
def test_api_transform_presentation_success():
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_PRESENTATION_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {
                "audience": "executive",
                "tone": "formal",
                "detail_level": "standard",
                "objective": "brief",
                "language": "English"
            }
        }
        response = client.post("/api/transform/presentation", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["presentation_title"] == SAMPLE_VALID_PRESENTATION_JSON["presentation_title"]
        assert len(data["slides"]) == 2
        assert data["slides"][0]["slide_number"] == 1

def test_api_transform_presentation_rejects_missing_model():
    response = client.post("/api/transform/presentation", json={})
    assert response.status_code == 422

def test_api_transform_presentation_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {"audience": "executive", "tone": "formal"}
        }
        response = client.post("/api/transform/presentation", json=payload)
        assert response.status_code == 503
        assert "Ensure Ollama is running" in response.json()["detail"]
