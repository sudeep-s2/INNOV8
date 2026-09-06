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
    ExecutiveSummaryTransformRequest,
    Audience,
    Tone,
    DetailLevel,
    Objective,
    Language,
)
from app.models.outputs import ExecutiveSummary
from app.services.transformations.executive_summary import ExecutiveSummaryGenerator
from app.services.base import (
    AIServiceValidationError,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from app.prompts.executive_summary import build_executive_summary_prompt

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

SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON = {
    "title": "Executive Strategic Summary: SCADA Infrastructure Cyber Threat",
    "overview": "A critical cyber intrusion was detected targeting 4 regional load dispatch centers by threat actor APT-44.",
    "key_findings": [
        "Four regional dispatch nodes experienced unauthorized telemetry reconnaissance.",
        "Zero-day exploit CVE-2026-38910 was leveraged to exfiltrate 4.8 GB of routing tables."
    ],
    "important_metrics_facts": [
        "4.8 GB data exfiltrated",
        "4 regional dispatch centers targeted"
    ],
    "risks_implications": [
        "Critical threat of grid desynchronization during peak load hours."
    ],
    "recommended_actions": [
        "Immediately isolate SCADA IEC-104 ports (TCP 2404) across all regional nodes."
    ],
    "source_references": [
        {
            "claim": "Four regional dispatch nodes targeted",
            "source_chunk_id": "chunk_1",
            "source_snippet": "Sensors detected unauthorized reconnaissance by APT-44"
        },
        {
            "claim": "Isolate SCADA IEC-104 ports",
            "source_chunk_id": "chunk_2",
            "source_snippet": "Isolate SCADA IEC-104 ports immediately"
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
def test_build_executive_summary_prompt_includes_config_and_canonical_data():
    config = TransformationConfig(
        audience=Audience.executive,
        tone=Tone.formal,
        detail_level=DetailLevel.detailed,
        objective=Objective.brief,
        language=Language.english
    )
    prompt = build_executive_summary_prompt(SAMPLE_STRUCTURED_MODEL, config)
    assert "Target Audience: executive" in prompt
    assert "Tone: formal" in prompt
    assert "Level of Detail: detailed" in prompt
    assert "Communication Objective: brief" in prompt
    assert "National SCADA Grid Cyber Intrusion" in prompt
    assert "chunk_1" in prompt
    assert "chunk_2" in prompt

# 2. Generator Unit Tests
@pytest.mark.asyncio
async def test_executive_summary_generator_success():
    generator = ExecutiveSummaryGenerator()
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON)}
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, ExecutiveSummary)
        assert result.title.startswith("Executive Strategic Summary")
        assert len(result.key_findings) == 2
        assert len(result.source_references) == 2
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_executive_summary_generator_corrective_retry_on_malformed_json():
    generator = ExecutiveSummaryGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "MALFORMED_NON_JSON"}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, ExecutiveSummary)
        assert result.title == SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON["title"]

@pytest.mark.asyncio
async def test_executive_summary_generator_corrective_retry_on_invalid_chunk_citation():
    generator = ExecutiveSummaryGenerator()
    # 1st attempt cites hallucinated chunk_99
    bad_json = dict(SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON)
    bad_json["source_references"] = [
        {"claim": "Invalid claim", "source_chunk_id": "chunk_99", "source_snippet": "bad"}
    ]
    bad_resp = create_mock_response(200, {"message": {"content": json.dumps(bad_json)}})
    good_resp = create_mock_response(200, {"message": {"content": json.dumps(SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON)}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, good_resp]
        result = await generator.transform(
            structured_model=SAMPLE_STRUCTURED_MODEL,
            config=TransformationConfig()
        )
        assert isinstance(result, ExecutiveSummary)
        assert result.source_references[0].source_chunk_id == "chunk_1"

@pytest.mark.asyncio
async def test_executive_summary_generator_fails_after_failed_retry():
    generator = ExecutiveSummaryGenerator()
    bad_resp = create_mock_response(200, {"message": {"content": "INVALID_JSON_STREAM"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_resp, bad_resp]
        with pytest.raises(AIServiceValidationError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

@pytest.mark.asyncio
async def test_executive_summary_generator_handles_ollama_connection_error():
    generator = ExecutiveSummaryGenerator()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(OllamaConnectionError):
            await generator.transform(
                structured_model=SAMPLE_STRUCTURED_MODEL,
                config=TransformationConfig()
            )

# 3. API Endpoint Tests (POST /api/transform/executive-summary)
def test_api_transform_executive_summary_success():
    mock_resp = create_mock_response(200, {
        "message": {"content": json.dumps(SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON)}
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
        response = client.post("/api/transform/executive-summary", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == SAMPLE_VALID_EXECUTIVE_SUMMARY_JSON["title"]
        assert len(data["key_findings"]) == 2
        assert len(data["source_references"]) == 2
        assert data["source_references"][0]["source_chunk_id"] == "chunk_1"

def test_api_transform_executive_summary_rejects_missing_model():
    response = client.post("/api/transform/executive-summary", json={})
    assert response.status_code == 422

def test_api_transform_executive_summary_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {"audience": "executive", "tone": "professional"}
        }
        response = client.post("/api/transform/executive-summary", json=payload)
        assert response.status_code == 503
        assert "Ensure Ollama is running" in response.json()["detail"]
