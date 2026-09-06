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
from app.models.transformation import (
    TransformationConfig,
    MultiTransformRequest,
    MultiTransformResponse,
    OutputType,
    Audience,
    Tone,
)
from app.models.outputs import (
    ExecutiveSummary,
    AdvisoryBrief,
    PublicCommunication,
    PresentationOutline,
    PresentationSlide,
    OutputSourceReference,
)
from app.services.transformations.orchestrator import TransformationOrchestrator
from app.services.base import OllamaConnectionError

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

MOCK_EXEC = ExecutiveSummary(
    title="Executive Summary",
    overview="Overview",
    key_findings=["Finding 1"],
    important_metrics_facts=["4.8 GB"],
    risks_implications=["Risk 1"],
    recommended_actions=["Action 1"],
    source_references=[OutputSourceReference(claim="Finding 1", source_chunk_id="chunk_1")]
)

MOCK_ADVISORY = AdvisoryBrief(
    title="Advisory Brief",
    situation_context="Context",
    key_observations=["Observation 1"],
    verified_facts=["Fact 1"],
    risk_impact="Critical",
    recommended_actions_directives=["Directive 1"],
    caveats=["Caveat 1"],
    source_references=[OutputSourceReference(claim="Observation 1", source_chunk_id="chunk_1")]
)

MOCK_PUBLIC = PublicCommunication(
    headline="Public Headline",
    opening="Opening",
    core_message="Core Message",
    explanation="Explanation",
    public_guidance="Guidance",
    source_references=[OutputSourceReference(claim="Core Message", source_chunk_id="chunk_1")]
)

MOCK_PRESENTATION = PresentationOutline(
    presentation_title="Deck Title",
    slides=[
        PresentationSlide(
            slide_number=1,
            title="Slide 1",
            key_points=["Point 1"],
            speaker_notes="Notes",
            source_references=[OutputSourceReference(claim="Point 1", source_chunk_id="chunk_1")]
        )
    ],
    source_references=[OutputSourceReference(claim="Deck Title", source_chunk_id="chunk_1")]
)

# 1. Orchestrator Service Unit Tests
@pytest.mark.asyncio
async def test_orchestrator_single_output_executive_summary():
    mock_exec_gen = AsyncMock()
    mock_exec_gen.transform.return_value = MOCK_EXEC

    orchestrator = TransformationOrchestrator(exec_generator=mock_exec_gen)
    result = await orchestrator.transform_multi(
        structured_model=SAMPLE_STRUCTURED_MODEL,
        config=TransformationConfig(),
        output_types=[OutputType.executive_summary]
    )

    assert result.topic == SAMPLE_STRUCTURED_MODEL.topic
    assert result.executive_summary is not None
    assert result.executive_summary.title == "Executive Summary"
    assert result.advisory_brief is None
    assert result.public_communication is None
    assert result.presentation is None
    assert len(result.errors) == 0

@pytest.mark.asyncio
async def test_orchestrator_multiple_outputs():
    mock_exec_gen = AsyncMock()
    mock_exec_gen.transform.return_value = MOCK_EXEC
    mock_advisory_gen = AsyncMock()
    mock_advisory_gen.transform.return_value = MOCK_ADVISORY

    orchestrator = TransformationOrchestrator(
        exec_generator=mock_exec_gen,
        advisory_generator=mock_advisory_gen
    )
    result = await orchestrator.transform_multi(
        structured_model=SAMPLE_STRUCTURED_MODEL,
        config=TransformationConfig(),
        output_types=[OutputType.executive_summary, OutputType.advisory_brief]
    )

    assert result.executive_summary is not None
    assert result.advisory_brief is not None
    assert result.public_communication is None
    assert result.presentation is None
    assert len(result.errors) == 0

@pytest.mark.asyncio
async def test_orchestrator_all_four_outputs():
    mock_exec_gen = AsyncMock()
    mock_exec_gen.transform.return_value = MOCK_EXEC
    mock_advisory_gen = AsyncMock()
    mock_advisory_gen.transform.return_value = MOCK_ADVISORY
    mock_public_gen = AsyncMock()
    mock_public_gen.transform.return_value = MOCK_PUBLIC
    mock_pres_gen = AsyncMock()
    mock_pres_gen.transform.return_value = MOCK_PRESENTATION

    orchestrator = TransformationOrchestrator(
        exec_generator=mock_exec_gen,
        advisory_generator=mock_advisory_gen,
        public_comm_generator=mock_public_gen,
        presentation_generator=mock_pres_gen
    )
    result = await orchestrator.transform_multi(
        structured_model=SAMPLE_STRUCTURED_MODEL,
        config=TransformationConfig(),
        output_types=[
            OutputType.executive_summary,
            OutputType.advisory_brief,
            OutputType.public_communication,
            OutputType.presentation
        ]
    )

    assert result.executive_summary is not None
    assert result.advisory_brief is not None
    assert result.public_communication is not None
    assert result.presentation is not None
    assert len(result.errors) == 0

@pytest.mark.asyncio
async def test_orchestrator_partial_failure_handling():
    mock_exec_gen = AsyncMock()
    mock_exec_gen.transform.return_value = MOCK_EXEC
    mock_advisory_gen = AsyncMock()
    mock_advisory_gen.transform.side_effect = OllamaConnectionError("Connection timeout on advisory")

    orchestrator = TransformationOrchestrator(
        exec_generator=mock_exec_gen,
        advisory_generator=mock_advisory_gen
    )
    result = await orchestrator.transform_multi(
        structured_model=SAMPLE_STRUCTURED_MODEL,
        config=TransformationConfig(),
        output_types=[OutputType.executive_summary, OutputType.advisory_brief]
    )

    # Executive summary succeeded
    assert result.executive_summary is not None
    # Advisory brief failed but is recorded in errors without crashing
    assert result.advisory_brief is None
    assert OutputType.advisory_brief.value in result.errors
    assert "Connection timeout" in result.errors[OutputType.advisory_brief.value]

# 2. API Endpoint Tests (POST /api/transform)
def test_api_multi_transform_endpoint_success():
    with patch("app.api.routes.transform.orchestrator.transform_multi", new_callable=AsyncMock) as mock_multi:
        mock_multi.return_value = MultiTransformResponse(
            topic=SAMPLE_STRUCTURED_MODEL.topic,
            executive_summary=MOCK_EXEC,
            advisory_brief=MOCK_ADVISORY
        )

        payload = {
            "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
            "config": {
                "audience": "executive",
                "tone": "formal"
            },
            "output_types": ["executive_summary", "advisory_brief"]
        }

        response = client.post("/api/transform", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == SAMPLE_STRUCTURED_MODEL.topic
        assert data["executive_summary"]["title"] == "Executive Summary"
        assert data["advisory_brief"]["title"] == "Advisory Brief"
        assert data["public_communication"] is None
        assert data["presentation"] is None

def test_api_multi_transform_rejects_empty_output_types():
    payload = {
        "structured_model": SAMPLE_STRUCTURED_MODEL.model_dump(),
        "config": {},
        "output_types": []
    }
    response = client.post("/api/transform", json=payload)
    assert response.status_code == 422  # Pydantic min_length=1 validation error

def test_api_multi_transform_rejects_missing_model():
    response = client.post("/api/transform", json={"output_types": ["executive_summary"]})
    assert response.status_code == 422
