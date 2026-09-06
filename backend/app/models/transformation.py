from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.models.content_model import StructuredContentModel
from app.models.outputs import (
    ExecutiveSummary,
    AdvisoryBrief,
    PublicCommunication,
    PresentationOutline
)

class Audience(str, Enum):
    general_public = "general_public"
    executive = "executive"
    technical = "technical"
    analyst = "analyst"

class Tone(str, Enum):
    professional = "professional"
    formal = "formal"
    informative = "informative"
    concise = "concise"

class DetailLevel(str, Enum):
    brief = "brief"
    standard = "standard"
    detailed = "detailed"

class Objective(str, Enum):
    inform = "inform"
    brief = "brief"
    summarize = "summarize"
    communicate = "communicate"

class Language(str, Enum):
    english = "English"

class OutputType(str, Enum):
    executive_summary = "executive_summary"
    advisory_brief = "advisory_brief"
    public_communication = "public_communication"
    presentation = "presentation"

class TransformationConfig(BaseModel):
    """User configuration parameters for controlling content transformation."""
    audience: Audience = Field(default=Audience.executive, description="Target reader audience")
    tone: Tone = Field(default=Tone.professional, description="Linguistic tone and style")
    detail_level: DetailLevel = Field(default=DetailLevel.standard, description="Level of detail/depth")
    objective: Objective = Field(default=Objective.inform, description="Primary communication goal")
    language: Language = Field(default=Language.english, description="Target output language")

class ExecutiveSummaryTransformRequest(BaseModel):
    """Request payload for generating an Executive Summary from a canonical model."""
    structured_model: StructuredContentModel = Field(..., description="Canonical StructuredContentModel from analysis")
    config: TransformationConfig = Field(default_factory=TransformationConfig, description="Transformation parameters")

class AdvisoryBriefTransformRequest(BaseModel):
    """Request payload for generating an Advisory Brief from a canonical model."""
    structured_model: StructuredContentModel = Field(..., description="Canonical StructuredContentModel from analysis")
    config: TransformationConfig = Field(default_factory=TransformationConfig, description="Transformation parameters")

class PublicCommunicationTransformRequest(BaseModel):
    """Request payload for generating a Public Communication artefact from a canonical model."""
    structured_model: StructuredContentModel = Field(..., description="Canonical StructuredContentModel from analysis")
    config: TransformationConfig = Field(default_factory=TransformationConfig, description="Transformation parameters")

class PresentationTransformRequest(BaseModel):
    """Request payload for generating a Presentation Outline from a canonical model."""
    structured_model: StructuredContentModel = Field(..., description="Canonical StructuredContentModel from analysis")
    config: TransformationConfig = Field(default_factory=TransformationConfig, description="Transformation parameters")

class MultiTransformRequest(BaseModel):
    """Request payload for orchestrating multiple transformations from the SAME canonical model."""
    structured_model: StructuredContentModel = Field(..., description="Single shared canonical StructuredContentModel")
    config: TransformationConfig = Field(default_factory=TransformationConfig, description="Shared transformation parameters")
    output_types: List[OutputType] = Field(..., min_length=1, description="List of target outputs to generate")

class MultiTransformResponse(BaseModel):
    """Unified response containing the generated output artefacts and any partial errors."""
    topic: str = Field(..., description="Topic of the analyzed source")
    executive_summary: Optional[ExecutiveSummary] = Field(None, description="Generated Executive Summary if requested")
    advisory_brief: Optional[AdvisoryBrief] = Field(None, description="Generated Advisory Brief if requested")
    public_communication: Optional[PublicCommunication] = Field(None, description="Generated Public Communication if requested")
    presentation: Optional[PresentationOutline] = Field(None, description="Generated Presentation Outline if requested")
    errors: Dict[str, str] = Field(default_factory=dict, description="Error messages for any failed transformation types")
