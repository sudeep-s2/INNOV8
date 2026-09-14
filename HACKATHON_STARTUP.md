# INNOV8 / Info2Impact — Hackathon Startup & Deployment Runbook

**Project**: Info2Impact (SIH26154: Gen AI Platform for Automated Content Transformation)  
**Organization**: National Technical Research Organisation (NTRO)  
**Team**: Innov8  
**Architecture**: React 19 + Vite (Vercel) → Cloudflare Tunnel → FastAPI Backend → Ollama Qwen3:8B (Local) with Groq Cloud Safety Fallback  

---

## 1. Quick Architecture Overview

```
[ Vercel Hosted React 19 SPA ]
              │
              ▼ HTTPS (Bypasses browser limits via Polling)
[ Cloudflare Quick Tunnel (*.trycloudflare.com) ]
              │
              ▼ HTTP
[ FastAPI Backend (Port 8000 on Windows) ]
        ┌─────┴────────────────────────┐
        ▼                              ▼
  [ Job Manager ]             [ Resilience Layer ]
(Async Polling Pattern)                │
        │                 ┌────────────┴────────────┐
        │                 ▼                         ▼
        └────────► [ Primary AI ]             [ Safety Fallback ]
                 Local Ollama (qwen3:8b)    Groq Cloud (llama-3.3-70b)
                   (100% On-Premises)          (Zero-Latency Cloud)
```

### Why the "Failed to fetch" error occurred and how it is fixed:
- **Root Cause**: Cloudflare Quick Tunnels enforce an edge proxy timeout of ~100 seconds for open HTTP connections. Previously, Stage 3 multi-output transformation (`POST /api/transform`) ran synchronous sequential inference across multiple deliverables on local CPU, taking 120–240 seconds. Cloudflare terminated the socket with `Incoming request ended abruptly: context canceled`, resulting in browser-level `Failed to fetch`.
- **Permanent Solution**: Both Canonical Analysis (`/api/ai/analyze`) and Multi-Output Transformation (`/api/transform`) now use the **Asynchronous Job Manager Pattern**:
  1. Frontend sends request (`POST /api/transform`).
  2. Backend immediately responds with HTTP 200 `{ "job_id": "job_...", "status": "processing" }` in **< 50ms**.
  3. Frontend polls `GET /api/transform/status/{job_id}` every 2.5s with non-blocking HTTP requests.
  4. Once complete, full validated deliverables are returned with 100% source grounding provenance.

---

## 2. Startup Commands (Three Terminals)

### Terminal 1: Start Local Ollama
```powershell
ollama run qwen3:8b
```
*Verify Ollama is ready*:
```powershell
curl http://localhost:11434/api/tags
```

### Terminal 2: Start FastAPI Backend
```powershell
cd d:\Dev\Projects\INNOV8\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Verify backend and fallback readiness*:
```powershell
curl http://localhost:8000/api/ready
```
Expected output:
```json
{
  "ready": true,
  "service": "info2impact",
  "ollama_online": true,
  "model": "qwen3:8b",
  "fallback_configured": true,
  "active_provider": "ollama"
}
```

### Terminal 3: Start Cloudflare Tunnel
```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000
```
*Note the public HTTPS URL printed in the terminal, for example*:
`https://example-random-words.trycloudflare.com`

---

## 3. Vercel Frontend Configuration

1. Open your Vercel Project Dashboard: `https://vercel.com/sudeep-s2/innov8`
2. Navigate to **Settings** → **Environment Variables**.
3. Add / Update:
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: `https://<YOUR-NEW-TUNNEL-URL>.trycloudflare.com` (no trailing slash)
4. Trigger a Redeploy (or click **Deployments** → **Redeploy**).

### For Local Frontend Development
```powershell
cd d:\Dev\Projects\INNOV8\frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 4. AI Safety Fallback (Groq Cloud)

The backend includes zero-touch automatic fallback to Groq Cloud in case:
- Local Ollama crashes or runs out of RAM/VRAM
- Local inference takes longer than 180s
- Hardware cannot keep up during live demo

### Configuration in `backend/.env` (Never committed to Git):
```ini
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

- When Ollama is healthy: **100% Local Inference (Ollama Qwen3 8B)**.
- When Ollama is offline or times out: **Transparently falls back to Groq Cloud in < 1s**.
- Grounding verification: Both engines pass through identical deterministic Pydantic schema validation and citation checks.

---

## 5. Verification Checklist

| Check | Command / Action | Expected Result |
|---|---|---|
| Backend Pytest Suite | `python -m pytest backend/tests -k "not test_live_ollama"` | 110 passed in ~28s |
| Frontend Production Build | `cd frontend && npm run build` | `tsc -b && vite build` 0 errors |
| Backend Health Check | `http://localhost:8000/api/health` | `{"status":"ok", "service":"info2impact"}` |
| Subsystem Readiness | `http://localhost:8000/api/ready` | `ready: true`, `ollama_online: true` |
| Async Transformation Status | `POST /api/transform` | Returns `{ "job_id": "...", "status": "processing" }` |

---

## 6. Live Presentation & Demo Flow (5-Minute Script)

1. **Stage 1 (Source Ingestion)**:
   - Open app on Vercel or localhost.
   - Point out header: NTRO problem statement SIH26154, Connected status pill.
   - Click `"Load Sample NTRO SCADA Incident"` to demonstrate cyber-defence telemetry input.
   - Click `"Analyze & Extract Canonical Model"`.
2. **Stage 2 (Canonical Intelligence Model)**:
   - Highlight the real-time extraction: Topic, Executed Facts, Entities, Timestamps, and Metrics.
   - Click any interactive **Provenance Pill** (`[chunk_1]`, `[chunk_2]`) to demonstrate forensic source traceability and zero hallucinations.
3. **Stage 3 (Audience & Deliverable Configuration)**:
   - Select multiple deliverables: Executive Summary, Advisory Brief, Public Communication, Presentation Deck.
   - Choose tone (Formal / Professional / Concise).
   - Click `"Generate Selected Outputs"`.
4. **Stage 4 & 5 (Orchestration & Verification)**:
   - Show asynchronous non-blocking synthesis.
   - Inspect tabbed outputs tailored specifically for Defence Leadership (Executive Summary), Operational Field Units (Advisory Brief), General Public (Press Release), and Strategic Briefings (Slide Deck).
