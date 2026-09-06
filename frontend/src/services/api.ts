import type {
  HealthResponse,
  IngestResponse,
  StructuredContentModel,
  SourceChunk,
  MultiTransformRequest,
  MultiTransformResponse
} from '../types';

/**
 * Resolves the backend API base URL:
 * 1. Checks VITE_API_BASE_URL (standard for Vercel -> Tunnel connection)
 * 2. Checks VITE_API_URL (backward compatibility)
 * 3. Falls back to '/api' for local Vite proxy development (or direct localhost)
 */
function resolveApiBase(): string {
  const envUrl = (
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    ''
  ).trim();

  if (envUrl) {
    const sanitized = envUrl.replace(/\/+$/, '');
    return sanitized.endsWith('/api') ? sanitized : `${sanitized}/api`;
  }

  // Local development fallback via Vite proxy (proxying to http://127.0.0.1:8000)
  return '/api';
}

const API_BASE = resolveApiBase();

// Standard headers to bypass tunnel interstitial warning pages (e.g. ngrok free tier, localtunnel)
const TUNNEL_HEADERS: Record<string, string> = {
  'ngrok-skip-browser-warning': 'true',
  'bypass-tunnel-reminder': 'true'
};

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`, {
    headers: {
      ...TUNNEL_HEADERS
    }
  });
  if (!response.ok) {
    throw new Error(`Health check failed with status: ${response.status}`);
  }
  return response.json();
}

export async function ingestText(text: string): Promise<IngestResponse> {
  const response = await fetch(`${API_BASE}/source/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...TUNNEL_HEADERS
    },
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
    headers: {
      ...TUNNEL_HEADERS
      // Note: do NOT set Content-Type header for FormData so browser computes boundary
    },
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
    headers: {
      'Content-Type': 'application/json',
      ...TUNNEL_HEADERS
    },
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
    headers: {
      'Content-Type': 'application/json',
      ...TUNNEL_HEADERS
    },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Transformation orchestration failed (HTTP ${response.status})`);
  }
  return response.json();
}
