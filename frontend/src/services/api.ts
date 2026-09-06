import type {
  HealthResponse,
  IngestResponse,
  StructuredContentModel,
  SourceChunk,
  MultiTransformRequest,
  MultiTransformResponse
} from '../types';

const API_BASE = '/api';

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status: ${response.status}`);
  }
  return response.json();
}

export async function ingestText(text: string): Promise<IngestResponse> {
  const response = await fetch(`${API_BASE}/source/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Text ingestion failed (HTTP ${response.status})`);
  }
  return response.json();
}

export async function uploadSourceFile(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/source/upload`, {
    method: 'POST',
    body: formData
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `File upload failed (HTTP ${response.status})`);
  }
  return response.json();
}

export async function analyzeSource(params: {
  source_text?: string;
  chunks?: SourceChunk[];
}): Promise<StructuredContentModel> {
  const response = await fetch(`${API_BASE}/ai/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Canonical analysis failed (HTTP ${response.status})`);
  }
  return response.json();
}

export async function transformOutputs(
  request: MultiTransformRequest
): Promise<MultiTransformResponse> {
  const response = await fetch(`${API_BASE}/transform`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Transformation orchestration failed (HTTP ${response.status})`);
  }
  return response.json();
}
