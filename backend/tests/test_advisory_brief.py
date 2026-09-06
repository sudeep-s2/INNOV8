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
    AdvisoryBriefTransformRequest,
    Audience,
    Tone,
    DetailLevel,
    Objective,
    Language,
)
from app.models.outputs import AdvisoryBrief
from app.services.transformations.advisory_brief import AdvisoryBriefGenerator
from app.services.base import (
    AIServiceValidationError,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from app.prompts.advisory_brief import build_advisory_brief_prompt

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
        RiskImplication(risk="Critical exposure of SCADA IEC-104 telemetry routing tables", severity="Critical", source_chunk_ids=["chunk_1"])
    ],
    recommendations=[
        RecommendationAction(action="Isolate SCADA IEC-104 ports (TCP 2404) immediately", priority="Immediate", source_chunk_ids=["chunk_2"]),
        RecommendationAction(action="Deploy emergency firmware hotfix KB-2026-08 across all gateway controllers within 24 hours", priority="Immediate", source_chunk_ids=["chunk_2"])
    ],
    important_statements=[
        ImportantStatement(statement="Emergency containment protocols initiated", source_chunk_ids=["chunk_2"])
    ],
    source_chunks=[
        SourceChunk(chunk_id="chunk_1", text="Sensors detected unauthorized reconnaissance by APT-44 exploiting CVE-2026-38910. 4.8 GB exfiltrated on 2026-08-10.", page_number=1),
        SourceChunk(chunk_id="chunk_2", text="Remediation: Isolate SCADA IEC-104 ports (TCP 2404) immediately. Deploy emergency firmware hotfix KB-2026-08.", page_number=2),
    ]
)

SAMPLE_VALID_ADVISORY_BRIEF_JSON = {
    "title": "TECHNICAL ADVISORY: SCADA IEC-104 Gateway Exploitation by APT-44",
    "situation_context": "Reconnaissance telemetry indicates targeted probing across 4 regional electrical dispatch nodes via zero-day exploit CVE-2026-38910.",
    "key_observations": [
        "Unauthenticated network telemetry traffic observed on TCP port 2404.",
        "4.8 GB of routing tables exfiltrated to external C2 endpoints on 2026-08-10."
    ],
    "verified_facts": [
        "CVE-2026-38910 confirmed present on edge industrial SCADA gateways.",
        "4 regional dispatch centers confirmed within threat blast radius."
    ],
    "risk_impact": "Critical: Threat actor possesses topology data enabling potential disruption of electrical frequency synchronization.",
    "recommended_actions_directives": [
        "MANDATORY: Isolate all external-facing SCADA IEC-104 ports (TCP 2404) immediately.",
        "MANDATORY: Apply security patch KB-2026-08 to all gateway controllers within 24 hours."
    ],
    "caveats": [
        "Assessment limited to TCP/IP gateway nodes; isolated serial RTU links not yet audited."
    ],
    "source_references": [
        {
            "claim": "Reconnaissance across 4 regional dispatch nodes",
            "source_chunk_id": "chunk_1",
            "source_snippet": "Sensors detected unauthorized reconnaissance by APT-44"
        },
        {
            "claim": "Isolate SCADA IEC-104 ports immediately",
            "source_chunk_id": "chunk_2",
            "source_snippet": "Isolate SCADA IEC-104 ports (TCP 2404) immediately"
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
def test_build_advisory_brief_prompt_includes_config_and_canonical_data():
    config = TransformationConfig(
        audience=Audience.technical,
        tone=Tone.formal,
        detail_level=DetailLevel.detailed,
        objective=Objective.inform,
        language=Language.english
    )
    prompt = build_advisory_brief_prompt(SAMPLE_STRUCTURED_MODEL, config)
    assert "Target Audience: technical" in prompt
    assert "Tone: formal" in prompt
    assert "Level of Detail: detailed" in prompt
    assert "National SCADA Grid Cyber Intrusion" in prompt
    assert "chunk_1" in prompt
    assert "chunk_2" in prompt

# 2. Generator Unit Tests
@pytest.mark.asyncio
async def test_advisory_brief_generator_success():
    generator = AdvisoryBriefGenerator()
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_ADVISORY_BRIEF_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig(audience=Audience.technical, tone=Tone.formal)
        )
        assert isinstance(result, AdvisoryBrief)
        assert result.title.startswith("TECHNICAL ADVISORY")
        assert len(result.key_observations) == 2
        assert len(result.recommended_actions_directives) == 2
        assert len(result.source_references) == 2
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_advisory_brief_generator_corrective_retry_on_malformed_json():
    generator = AdvisoryBriefGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "INVALID_JSON_STREAM"}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_ADVISORY_BRIEF_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, AdvisoryBrief)
        assert result.title == SAMPLE_VALID_ADVISORY_BRIEF_JSON["title"]

@pytest.mark.asyncio
async def test_advisory_brief_generator_corrective_retry_on_invalid_chunk_citation():
    generator = AdvisoryBriefGenerator()
    # 1st attempt cites hallucinated chunk_99
    bad_json = dict(SAMPLE_VALID_ADVISORY_BRIEF_JSON)
    bad_json["source_references"] = [
        {"claim": "Invalid claim", "source_chunk_id": "chunk_99", "source_snippet": "bad"}
    ]
    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_json)}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_ADVISORY_BRIEF_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, AdvisoryBrief)
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_advisory_brief_generator_fails_after_failed_retry():
    generator = AdvisoryBriefGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "MALFORMED_JSON_AGAIN"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

@pytest.mark.asyncio
async def test_advisory_brief_generator_handles_ollama_connection_error():
    generator = AdvisoryBriefGenerator()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(OllamaConnectionError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

# 3. API Endpoint Tests (POST /api/transform/advisory-brief)
def test_api_transform_advisory_brief_success():
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_ADVISORY_BRIEF_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {
                "audience": "technical",
                "tone": "formal",
                "detail_level": "detailed",
                "objective": "inform",
                "language": "English"
            }
        }
        response = client.post("/api/transform/advisory-brief", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == SAMPLE_VALID_ADVISORY_BRIEF_JSON["title"]
        assert len(data["key_observations"]) == 2
        assert len(data["recommended_actions_directives"]) == 2
        assert len(data["source_references"]) == 2
        assert data["source_references"][0]["source_chunk_id"] == "chunk_1"

def test_api_transform_advisory_brief_rejects_missing_model():
    response = client.post("/api/transform/advisory-brief", json={})
    assert response.status_code == 422

def test_api_transform_advisory_brief_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {"audience": "technical", "tone": "formal"}
        }
        response = client.post("/api/transform/advisory-brief", json=payload)
        assert response.status_code == 503
        assert "Ensure Ollama is running" in response.json()["detail"]
