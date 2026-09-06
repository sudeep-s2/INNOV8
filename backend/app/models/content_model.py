from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.source import SourceChunk

class KeyFact(BaseModel):
    fact_id: str = Field(..., description="Unique fact identifier (e.g. 'fact_1')")
    statement: str = Field(..., description="Direct factual statement extracted from source")
    metric_or_date: Optional[str] = Field(None, description="Quantitative value or date if associated")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks supporting this fact")

class Entity(BaseModel):
    name: str = Field(..., description="Name of organization, system, place, or person")
    category: Optional[str] = Field(None, description="Entity classification (e.g. 'system', 'organization', 'cve')")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks mentioning this entity")

class EventDate(BaseModel):
    event: str = Field(..., description="Description of event or milestone")
    date_or_time: str = Field(..., description="Reported date, timestamp, or timeline")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks referencing this event")

class MetricNumber(BaseModel):
    metric: str = Field(..., description="Name of indicator or metric")
    value: str = Field(..., description="Quantity, percentage, or currency figure")
    context: Optional[str] = Field(None, description="Contextual description of the metric")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks containing this metric")

class RiskImplication(BaseModel):
    risk: str = Field(..., description="Identified vulnerability, hazard, or threat")
    severity: Optional[str] = Field(None, description="Severity level: High, Medium, Low, Critical")
    mitigation: Optional[str] = Field(None, description="Mentioned mitigation directive if present")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks identifying this risk")

class RecommendationAction(BaseModel):
    action: str = Field(..., description="Concrete actionable recommendation or directive")
    priority: Optional[str] = Field(None, description="Priority rating: Immediate, High, Medium, Standard")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks proposing this action")

class ImportantStatement(BaseModel):
    statement: str = Field(..., description="Key authoritative policy or operational assertion")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of source chunks containing this statement")

class StructuredContentModel(BaseModel):
    """Canonical intermediate representation extracted from source content in a single pass.
    All downstream transformations consume this shared model to ensure cross-artefact factual consistency.
    """
    topic: str = Field(..., min_length=1, description="Primary subject domain and focus of source")
    summary: str = Field(..., min_length=1, description="Comprehensive high-level neutral synopsis")
    key_facts: List[KeyFact] = Field(default_factory=list, description="Verified factual findings")
    entities: List[Entity] = Field(default_factory=list, description="Explicitly mentioned entities")
    dates: List[EventDate] = Field(default_factory=list, description="Timeline and chronological events")
    metrics: List[MetricNumber] = Field(default_factory=list, description="Quantitative data points and statistics")
    risks: List[RiskImplication] = Field(default_factory=list, description="Operational risks and hazards")
    recommendations: List[RecommendationAction] = Field(default_factory=list, description="Actionable recommendations")
    important_statements: List[ImportantStatement] = Field(default_factory=list, description="Authoritative statements")
    source_chunks: List[SourceChunk] = Field(default_factory=list, description="Indexed source chunks")
