// Domain Contracts matching FastAPI Backend Pydantic Models

export type Audience = 'general_public' | 'executive' | 'technical' | 'analyst';
export type Tone = 'professional' | 'formal' | 'informative' | 'concise';
export type DetailLevel = 'brief' | 'standard' | 'detailed';
export type Objective = 'inform' | 'brief' | 'summarize' | 'communicate';
export type Language = 'English';

export type OutputType = 'executive_summary' | 'advisory_brief' | 'public_communication' | 'presentation';

export interface SourceChunk {
  chunk_id: string;
  text: string;
  page_number?: number;
  source_location?: string;
  char_start?: number;
  char_end?: number;
}

export interface TransformationConfig {
  audience: Audience;
  tone: Tone;
  detail_level: DetailLevel;
  objective: Objective;
  language: Language;
}

export interface KeyFact {
  fact_id: string;
  statement: string;
  metric_or_date?: string;
  source_chunk_ids: string[];
}

export interface Entity {
  name: string;
  category?: string;
  source_chunk_ids: string[];
}

export interface EventDate {
  event: string;
  date_or_time: string;
  source_chunk_ids: string[];
}

export interface MetricNumber {
  metric: string;
  value: string;
  context?: string;
  source_chunk_ids: string[];
}

export interface RiskImplication {
  risk: string;
  severity?: string;
  mitigation?: string;
  source_chunk_ids: string[];
}

export interface RecommendationAction {
  action: string;
  priority?: string;
  source_chunk_ids: string[];
}

export interface ImportantStatement {
  statement: string;
  source_chunk_ids: string[];
}

export interface StructuredContentModel {
  topic: string;
  summary: string;
  key_facts: KeyFact[];
  entities: Entity[];
  dates: EventDate[];
  metrics: MetricNumber[];
  risks: RiskImplication[];
  recommendations: RecommendationAction[];
  important_statements: ImportantStatement[];
  source_chunks: SourceChunk[];
}

export interface OutputSourceReference {
  claim: string;
  source_chunk_id: string;
  source_snippet?: string;
}

export interface ExecutiveSummary {
  title: string;
  overview: string;
  key_findings: string[];
  important_metrics_facts: string[];
  risks_implications: string[];
  recommended_actions: string[];
  source_references: OutputSourceReference[];
}

export interface AdvisoryBrief {
  title: string;
  situation_context: string;
  key_observations: string[];
  verified_facts: string[];
  risk_impact: string;
  recommended_actions_directives: string[];
  caveats: string[];
  source_references: OutputSourceReference[];
}

export interface PublicCommunication {
  headline: string;
  opening: string;
  core_message: string;
  explanation: string;
  public_guidance: string;
  source_references: OutputSourceReference[];
}

export interface PresentationSlide {
  slide_number: number;
  title: string;
  key_points: string[];
  data_highlights?: string;
  speaker_notes: string;
  source_references: OutputSourceReference[];
}

export interface PresentationOutline {
  presentation_title: string;
  slides: PresentationSlide[];
  source_references: OutputSourceReference[];
}

export interface MultiTransformRequest {
  structured_model: StructuredContentModel;
  config: TransformationConfig;
  output_types: OutputType[];
}

export interface MultiTransformResponse {
  topic: string;
  executive_summary?: ExecutiveSummary | null;
  advisory_brief?: AdvisoryBrief | null;
  public_communication?: PublicCommunication | null;
  presentation?: PresentationOutline | null;
  errors: Record<string, string>;
}

export interface IngestResponse {
  filename?: string;
  total_characters: number;
  total_chunks: number;
  chunks: SourceChunk[];
}

export interface HealthResponse {
  status: string;
  service: string;
}
