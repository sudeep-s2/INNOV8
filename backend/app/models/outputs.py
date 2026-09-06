from typing import List, Optional
from pydantic import BaseModel, Field

class OutputSourceReference(BaseModel):
    """Citation linking a generated claim or finding back to an authoritative source chunk."""
    claim: str = Field(..., description="Factual claim made in the output")
    source_chunk_id: str = Field(..., description="ID of source chunk that directly supports this claim")
    source_snippet: Optional[str] = Field(None, description="Direct supporting quote or excerpt from the source chunk")

class ExecutiveSummary(BaseModel):
    """Output contract for strategic leadership executive summary."""
    title: str = Field(..., description="Strategic executive title")
    overview: str = Field(..., description="High-level narrative synthesis for executive decision-makers")
    key_findings: List[str] = Field(default_factory=list, description="Core strategic findings")
    important_metrics_facts: List[str] = Field(default_factory=list, description="Critical numbers, timelines, and statistics")
    risks_implications: List[str] = Field(default_factory=list, description="Strategic, organizational, or operational risks")
    recommended_actions: List[str] = Field(default_factory=list, description="Prioritized strategic directives and next steps")
    source_references: List[OutputSourceReference] = Field(default_factory=list, description="Source grounding citations")

class AdvisoryBrief(BaseModel):
    """Output contract for formal operational and technical security advisories."""
    title: str = Field(..., description="Formal advisory title and threat descriptor")
    situation_context: str = Field(..., description="Operational background and context of current situation")
    key_observations: List[str] = Field(default_factory=list, description="Direct technical and operational observations")
    verified_facts: List[str] = Field(default_factory=list, description="Telemetry and substantiated data points")
    risk_impact: str = Field(..., description="Detailed threat exposure, vulnerability analysis, and blast radius")
    recommended_actions_directives: List[str] = Field(default_factory=list, description="Mandatory containment and remediation directives")
    caveats: List[str] = Field(default_factory=list, description="Operational boundaries, data limitations, or assumptions")
    source_references: List[OutputSourceReference] = Field(default_factory=list, description="Source grounding citations")

class PublicCommunication(BaseModel):
    """Output contract for clear, jargon-free public releases and citizen communication."""
    headline: str = Field(..., description="Clear, engaging public headline")
    opening: str = Field(..., description="Attention-capturing opening paragraph")
    core_message: str = Field(..., description="Primary takeaway in accessible, plain language")
    explanation: str = Field(..., description="Context and significance explained without unnecessary technical jargon")
    public_guidance: str = Field(..., description="Actionable public advice, reassurance, or next steps")
    source_references: List[OutputSourceReference] = Field(default_factory=list, description="Source grounding citations")

class PresentationSlide(BaseModel):
    """Individual slide within a presentation outline."""
    slide_number: int = Field(..., ge=1, description="Slide sequence index (1, 2, ...)")
    title: str = Field(..., description="Slide headline")
    key_points: List[str] = Field(default_factory=list, description="Concise bullet points for slide visual")
    data_highlights: Optional[str] = Field(None, description="Key statistic, figure, or callout for this slide")
    speaker_notes: str = Field(..., description="Spoken script for the presenter delivering this slide")
    source_references: List[OutputSourceReference] = Field(default_factory=list, description="Source grounding citations for this slide")

class PresentationOutline(BaseModel):
    """Output contract for slide-by-slide briefing deck outline."""
    presentation_title: str = Field(..., description="Overall presentation title")
    slides: List[PresentationSlide] = Field(default_factory=list, description="Ordered sequence of slides")
    source_references: List[OutputSourceReference] = Field(default_factory=list, description="Overall presentation grounding citations")
