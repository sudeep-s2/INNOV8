import pytest
from pydantic import ValidationError
from app.models import (
    SourceChunk,
    TransformationConfig,
    Audience,
    Tone,
    DetailLevel,
    Objective,
    Language,
    StructuredContentModel,
    KeyFact,
    Entity,
    EventDate,
    MetricNumber,
    RiskImplication,
    RecommendationAction,
    ImportantStatement,
    OutputSourceReference,
    ExecutiveSummary,
    AdvisoryBrief,
    PublicCommunication,
    PresentationSlide,
    PresentationOutline
)

# 1. SourceChunk Tests
def test_source_chunk_valid():
    chunk = SourceChunk(
        chunk_id="chunk_1",
        text="Sample intelligence report paragraph regarding SCADA protocols.",
        page_number=1,
        source_location="Section 1",
        char_start=0,
        char_end=64
    )
    assert chunk.chunk_id == "chunk_1"
    assert chunk.page_number == 1
    assert chunk.char_end == 64

def test_source_chunk_invalid_empty_fields():
    with pytest.raises(ValidationError):
        SourceChunk(chunk_id="", text="")

def test_source_chunk_invalid_negative_offset():
    with pytest.raises(ValidationError):
        SourceChunk(chunk_id="chunk_1", text="valid", char_start=-5)

# 2. TransformationConfig Tests
def test_transformation_config_defaults():
    config = TransformationConfig()
    assert config.audience == Audience.executive
    assert config.tone == Tone.professional
    assert config.detail_level == DetailLevel.standard
    assert config.objective == Objective.inform
    assert config.language == Language.english

def test_transformation_config_valid_custom():
    config = TransformationConfig(
        audience=Audience.technical,
        tone=Tone.formal,
        detail_level=DetailLevel.detailed,
        objective=Objective.summarize,
        language=Language.english
    )
    assert config.audience == Audience.technical
    assert config.tone == Tone.formal
    assert config.detail_level == DetailLevel.detailed

def test_transformation_config_rejects_invalid_enum():
    with pytest.raises(ValidationError):
        TransformationConfig(audience="invalid_audience_type")  # type: ignore

    with pytest.raises(ValidationError):
        TransformationConfig(tone="sarcastic")  # type: ignore

# 3. StructuredContentModel Tests
def test_structured_content_model_valid():
    model = StructuredContentModel(
        topic="Power Grid SCADA Threat Telemetry",
        summary="A zero-day exploit targeting regional dispatch centers was detected.",
        key_facts=[
            KeyFact(fact_id="f1", statement="14 sub-stations compromised", metric_or_date="14", source_chunk_ids=["chunk_1"])
        ],
        entities=[
            Entity(name="APT-44", category="threat_actor"),
            Entity(name="Apex Automation", category="vendor")
        ],
        dates=[
            EventDate(event="Initial breach", date_or_time="2026-08-10", source_chunk_ids=["chunk_1"])
        ],
        metrics=[
            MetricNumber(metric="Data Exfiltrated", value="4.8 GB", context="C2 transfer", source_chunk_ids=["chunk_2"])
        ],
        risks=[
            RiskImplication(risk="Grid desynchronization", severity="Critical", mitigation="Air gap ports", source_chunk_ids=["chunk_3"])
        ],
        recommendations=[
            RecommendationAction(action="Deploy hotfix KB-2026", priority="Immediate", source_chunk_ids=["chunk_3"])
        ],
        important_statements=[
            ImportantStatement(statement="Fail-safe interlocks prevented blackout", source_chunk_ids=["chunk_1"])
        ],
        source_chunks=[
            SourceChunk(chunk_id="chunk_1", text="Breach telemetry text...")
        ]
    )
    assert model.topic == "Power Grid SCADA Threat Telemetry"
    assert len(model.key_facts) == 1
    assert model.key_facts[0].source_chunk_ids == ["chunk_1"]
    assert len(model.entities) == 2

def test_structured_content_model_requires_topic_and_summary():
    with pytest.raises(ValidationError):
        StructuredContentModel(topic="", summary="")

# 4. Output Contracts Tests
def test_executive_summary_valid():
    summary = ExecutiveSummary(
        title="Executive Summary: SCADA Cyber Incident",
        overview="High-level synthesis of grid security incident.",
        key_findings=["Finding 1", "Finding 2"],
        important_metrics_facts=["4.8 GB exfiltrated", "14 nodes affected"],
        risks_implications=["Operational disruption risk"],
        recommended_actions=["Immediate network isolation"],
        source_references=[
            OutputSourceReference(claim="14 nodes affected", source_chunk_id="chunk_1", source_snippet="14 state-level nodes")
        ]
    )
    assert summary.title == "Executive Summary: SCADA Cyber Incident"
    assert len(summary.key_findings) == 2
    assert len(summary.source_references) == 1

def test_executive_summary_missing_required():
    with pytest.raises(ValidationError):
        ExecutiveSummary(title="Incomplete")  # type: ignore

def test_advisory_brief_valid():
    advisory = AdvisoryBrief(
        title="ADVISORY: IEC-104 Protocol Vulnerability",
        situation_context="Telemetry anomalies detected on regional dispatch nodes.",
        key_observations=["Observation 1"],
        verified_facts=["CVE-2026-38910 verified"],
        risk_impact="Critical vulnerability with CVSS 9.8.",
        recommended_actions_directives=["Block TCP Port 2404"],
        caveats=["Serial links not yet analyzed"],
        source_references=[]
    )
    assert advisory.title.startswith("ADVISORY")
    assert "CVSS 9.8" in advisory.risk_impact

def test_public_communication_valid():
    pub = PublicCommunication(
        headline="National Grid Advisory: Security Measures Underway",
        opening="Grid security authorities are monitoring critical infrastructure.",
        core_message="Electrical services remain fully stable and uninterrupted.",
        explanation="Protective systems activated automatically to maintain reliability.",
        public_guidance="No action is required from citizens.",
        source_references=[]
    )
    assert pub.headline == "National Grid Advisory: Security Measures Underway"
    assert "stable" in pub.core_message

def test_presentation_outline_valid():
    deck = PresentationOutline(
        presentation_title="SCADA Grid Threat Briefing",
        slides=[
            PresentationSlide(
                slide_number=1,
                title="Executive Overview",
                key_points=["Threat actor APT-44 identified", "Zero-day exploited"],
                data_highlights="18 OT networks exposed",
                speaker_notes="Good morning leadership, today we brief the SCADA incident..."
            ),
            PresentationSlide(
                slide_number=2,
                title="Remediation Plan",
                key_points=["Immediate port blocking", "Firmware rollout"],
                speaker_notes="Here is the immediate 6-hour remediation timeline..."
            )
        ]
    )
    assert len(deck.slides) == 2
    assert deck.slides[0].slide_number == 1
    assert "APT-44" in deck.slides[0].key_points[0]
