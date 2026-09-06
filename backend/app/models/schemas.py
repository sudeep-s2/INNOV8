from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# --- Grounding & Chunking Models ---

class SourceChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk identifier (e.g. 'chunk_1')")
    title: str = Field("General Content", description="Section header or title")
    content: str = Field(..., description="Text content of the chunk")
    page_number: Optional[int] = Field(None, description="Page number in original document if PDF")
    char_start: Optional[int] = None
    char_end: Optional[int] = None

class GroundingCitation(BaseModel):
    claim: str = Field(..., description="Factual claim or statement made in the output")
    source_chunk_id: str = Field(..., description="ID of source chunk that supports this claim")
    source_title: str = Field("", description="Title of the source section/chunk")
    source_snippet: str = Field(..., description="Excerpt or supporting quote from source chunk")
    confidence: float = Field(1.0, description="Confidence score of the grounding (0.0 - 1.0)")

class StructuredFact(BaseModel):
    fact_id: str = Field(..., description="Unique fact ID (e.g. 'fact_1')")
    statement: str = Field(..., description="Clear factual statement extracted from source")
    metric_or_date: Optional[str] = Field(None, description="Associated number, metric, or date if present")
    category: str = Field("finding", description="Category: finding, risk, recommendation, metric, background")
    source_chunk_id: str = Field(..., description="ID of supporting source chunk")

# --- Intermediate Structured Content Model (Shared JSON Representation) ---

class StructuredContentModel(BaseModel):
    main_topic: str = Field(..., description="Primary subject and purpose of the source text")
    summary: str = Field(..., description="High-level neutral synopsis of the entire document")
    key_facts: List[StructuredFact] = Field(default_factory=list, description="Core verified facts")
    entities: List[str] = Field(default_factory=list, description="Organizations, individuals, systems, or places")
    events_and_dates: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological events and dates")
    numbers_and_metrics: List[Dict[str, Any]] = Field(default_factory=list, description="Quantitative statistics, counts, percentages")
    risks_and_implications: List[Dict[str, Any]] = Field(default_factory=list, description="Identified hazards, vulnerabilities, or consequences")
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="Actionable recommendations or guidance")
    important_statements: List[Dict[str, Any]] = Field(default_factory=list, description="Key policy or authoritative assertions")
    source_chunks: List[SourceChunk] = Field(default_factory=list, description="Original segmented source chunks")

# --- Transformation Configuration ---

AudienceType = Literal["General Public", "Executive", "Technical", "Analyst"]
ToneType = Literal["Professional", "Formal", "Informative", "Concise"]
DetailLevel = Literal["Brief", "Standard", "Detailed"]
ObjectiveType = Literal["Inform", "Brief", "Summarize", "Communicate"]
OutputType = Literal["executive_summary", "advisory_brief", "public_communication", "presentation_outline"]

class TransformationConfig(BaseModel):
    target_audience: AudienceType = Field("Executive", description="Intended reader audience")
    tone: ToneType = Field("Professional", description="Style and voice of output")
    level_of_detail: DetailLevel = Field("Standard", description="Depth and length of transformation")
    objective: ObjectiveType = Field("Inform", description="Core communication goal")
    language: str = Field("English", description="Target language (English supported in V1)")
    custom_notes: Optional[str] = Field(None, description="Optional special instructions")

# --- Specific Output Models ---

class ExecutiveSummaryOutput(BaseModel):
    title: str = Field(..., description="Impactful title for the executive summary")
    executive_overview: str = Field(..., description="Concise high-level synthesis for leadership")
    key_findings: List[str] = Field(default_factory=list, description="Core critical findings")
    important_facts_and_numbers: List[str] = Field(default_factory=list, description="Key statistics and metrics")
    risks_or_implications: List[str] = Field(default_factory=list, description="Identified organizational or operational risks")
    recommended_actions: List[str] = Field(default_factory=list, description="Strategic decisions and recommended next steps")
    source_grounding: List[GroundingCitation] = Field(default_factory=list, description="Claims mapped to source chunks")

class AdvisoryBriefOutput(BaseModel):
    title: str = Field(..., description="Advisory title and advisory classification")
    situation_context: str = Field(..., description="Operational background and context of current situation")
    key_observations: List[str] = Field(default_factory=list, description="Direct tactical observations")
    relevant_facts: List[str] = Field(default_factory=list, description="Substantiated facts and telemetry")
    risk_and_impact_assessment: str = Field(..., description="Analysis of threats, vulnerabilities, and impact scope")
    recommended_actions: List[str] = Field(default_factory=list, description="Concrete immediate and long-term actions")
    important_caveats: List[str] = Field(default_factory=list, description="Operational boundaries, data limitations, or assumptions")
    source_grounding: List[GroundingCitation] = Field(default_factory=list, description="Claims mapped to source chunks")

class PublicCommOutput(BaseModel):
    title: str = Field(..., description="Engaging, clear headline suitable for public release")
    opening_hook: str = Field(..., description="Engaging opening statement")
    main_message: str = Field(..., description="Core narrative message in clear, jargon-free language")
    supporting_facts: List[str] = Field(default_factory=list, description="Key facts accessible to the general public")
    plain_language_explanation: str = Field(..., description="Detailed context explained simply without technical obscurity")
    closing_statement: str = Field(..., description="Forward-looking concluding statement or public guidance")
    source_grounding: List[GroundingCitation] = Field(default_factory=list, description="Claims mapped to source chunks")

class PresentationSlide(BaseModel):
    slide_number: int = Field(..., description="Slide sequence number (1, 2, ...)")
    title: str = Field(..., description="Slide headline")
    key_points: List[str] = Field(default_factory=list, description="Bullet points for the slide visual")
    supporting_information: Optional[str] = Field(None, description="Data callout or brief subtitle")
    speaker_notes: str = Field(..., description="Detailed talking script for the presenter")
    source_grounding: List[GroundingCitation] = Field(default_factory=list, description="Claims mapped to source chunks")

class PresentationOutput(BaseModel):
    presentation_title: str = Field(..., description="Overall presentation title")
    target_audience: str = Field(..., description="Audience tailored for")
    estimated_duration_minutes: int = Field(15, description="Estimated speaking time")
    slides: List[PresentationSlide] = Field(default_factory=list, description="Slide sequence")
    source_grounding: List[GroundingCitation] = Field(default_factory=list, description="Overall presentation grounding citations")

# --- Ingestion & API Contracts ---

class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Raw text content to transform")
    title: Optional[str] = Field("Uploaded Document", description="Optional title")

class IngestResponse(BaseModel):
    source_id: str
    title: str
    total_characters: int
    total_words: int
    chunks: List[SourceChunk]
    raw_text: str

class ValidationResult(BaseModel):
    is_valid: bool
    score: float = 1.0
    issues: List[str] = Field(default_factory=list)
    retried: bool = False

class SingleOutputResponse(BaseModel):
    output_type: OutputType
    title: str
    raw_markdown: str
    structured_data: Dict[str, Any]
    source_grounding: List[GroundingCitation]
    validation: ValidationResult

class TransformRequest(BaseModel):
    source_text: Optional[str] = None
    chunks: Optional[List[SourceChunk]] = None
    structured_model: Optional[StructuredContentModel] = None
    output_types: List[OutputType] = Field(
        default=["executive_summary", "advisory_brief", "public_communication", "presentation_outline"],
        min_length=1
    )
    config: TransformationConfig = Field(default_factory=TransformationConfig)

class TransformResponse(BaseModel):
    source_id: str
    structured_model: StructuredContentModel
    outputs: Dict[OutputType, SingleOutputResponse]
    execution_time_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RegenerateRequest(BaseModel):
    structured_model: StructuredContentModel
    output_type: OutputType
    config: TransformationConfig

class SampleDocument(BaseModel):
    id: str
    title: str
    category: str
    description: str
    content: str
