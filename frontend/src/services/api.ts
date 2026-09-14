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

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_DURATION_MS = 15 * 60 * 1000; // 15 minutes for CPU inference

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface AnalysisJobStatusResponse {
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  result?: StructuredContentModel;
  error?: string;
  [key: string]: any;
}

export async function analyzeSource(
  params: {
    source_text?: string;
    chunks?: SourceChunk[];
  },
  onStatusUpdate?: (status: string) => void
): Promise<StructuredContentModel> {
  // Step 1: Dispatch the background analysis job
  const initResponse = await fetch(`${API_BASE}/ai/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...TUNNEL_HEADERS
    },
    body: JSON.stringify(params)
  });

  if (!initResponse.ok) {
    const errorData = await initResponse.json().catch(() => ({}));
    throw new Error(errorData.detail || `Canonical analysis initiation failed (HTTP ${initResponse.status})`);
  }

  const initData = await initResponse.json();

  // If server responded with direct StructuredContentModel (sync fallback)
  if (initData.topic && initData.key_facts) {
    return initData as StructuredContentModel;
  }

  const jobId = initData.job_id;
  if (!jobId) {
    throw new Error('Analysis service did not return a valid job identifier.');
  }

  onStatusUpdate?.('Processing analysis job...');

  // Step 2: Poll status endpoint periodically
  const startTime = Date.now();

  while (Date.now() - startTime < MAX_POLL_DURATION_MS) {
    await sleep(POLL_INTERVAL_MS);

    try {
      const statusResponse = await fetch(`${API_BASE}/ai/analyze/status/${jobId}`, {
        headers: {
          ...TUNNEL_HEADERS
        }
      });

      if (!statusResponse.ok) {
        if (statusResponse.status === 404) {
          throw new Error(`Analysis job ${jobId} not found.`);
        }
        console.warn(`Status polling received HTTP ${statusResponse.status}, retrying...`);
        continue;
      }

      const statusData: AnalysisJobStatusResponse = await statusResponse.json();

      if (statusData.status === 'completed') {
        const canonicalModel = statusData.result || (statusData as unknown as StructuredContentModel);
        if (!canonicalModel || !canonicalModel.topic) {
          throw new Error('Analysis completed but did not return a valid StructuredContentModel.');
        }
        return canonicalModel;
      }

      if (statusData.status === 'failed') {
        throw new Error(statusData.error || 'Canonical analysis failed during background processing.');
      }

      onStatusUpdate?.('Deconstructing factual model with local Qwen3:8B...');
    } catch (pollErr: any) {
      if (
        pollErr.message &&
        (pollErr.message.includes('Canonical analysis failed') ||
          pollErr.message.includes('not found'))
      ) {
        throw pollErr;
      }
      console.warn('Transient polling error:', pollErr);
    }
  }

  throw new Error('Analysis request timed out waiting for local Qwen3:8B inference to complete.');
}

export interface TransformJobStatusResponse {
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  result?: MultiTransformResponse;
  error?: string;
  [key: string]: any;
}

export async function transformOutputs(
  request: MultiTransformRequest,
  onStatusUpdate?: (status: string) => void
): Promise<MultiTransformResponse> {
  // Step 1: Dispatch asynchronous transformation job
  const initResponse = await fetch(`${API_BASE}/transform`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...TUNNEL_HEADERS
    },
    body: JSON.stringify(request)
  });

  if (!initResponse.ok) {
    const errorData = await initResponse.json().catch(() => ({}));
    throw new Error(errorData.detail || `Transformation initiation failed (HTTP ${initResponse.status})`);
  }

  const initData = await initResponse.json();

  // If server responded synchronously (sync fallback or test environment)
  if (initData.topic && (initData.executive_summary !== undefined || initData.advisory_brief !== undefined)) {
    return initData as MultiTransformResponse;
  }

  const jobId = initData.job_id;
  if (!jobId) {
    throw new Error('Transformation service did not return a valid job identifier.');
  }

  onStatusUpdate?.('Dispatching deliverables to AI synthesis engine...');

  // Step 2: Poll status endpoint periodically
  const startTime = Date.now();
  let pollCount = 0;

  while (Date.now() - startTime < MAX_POLL_DURATION_MS) {
    await sleep(POLL_INTERVAL_MS);
    pollCount++;

    try {
      const statusResponse = await fetch(`${API_BASE}/transform/status/${jobId}`, {
        headers: {
          ...TUNNEL_HEADERS
        }
      });

      if (!statusResponse.ok) {
        if (statusResponse.status === 404) {
          throw new Error(`Transformation job ${jobId} not found.`);
        }
        console.warn(`Transform status polling HTTP ${statusResponse.status}, retrying...`);
        continue;
      }

      const statusData: TransformJobStatusResponse = await statusResponse.json();

      if (statusData.status === 'completed') {
        const responseData = statusData.result || (statusData as unknown as MultiTransformResponse);
        if (!responseData || !responseData.topic) {
          throw new Error('Transformation completed but did not return valid output payloads.');
        }
        return responseData;
      }

      if (statusData.status === 'failed') {
        throw new Error(statusData.error || 'Transformation failed during background processing.');
      }

      if (pollCount % 4 === 0) {
        onStatusUpdate?.('Synthesizing structured deliverables with source grounding verification...');
      } else if (pollCount % 2 === 0) {
        onStatusUpdate?.('Generating audience-adapted content artefacts...');
      }
    } catch (pollErr: any) {
      if (
        pollErr.message &&
        (pollErr.message.includes('Transformation failed') ||
          pollErr.message.includes('not found'))
      ) {
        throw pollErr;
      }
      console.warn('Transient transform polling error:', pollErr);
    }
  }

  throw new Error('Transformation request timed out waiting for AI synthesis to complete.');
}

