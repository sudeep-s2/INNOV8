import json
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.job_manager import get_job_manager, JobStatus
from app.models.content_model import StructuredContentModel

client = TestClient(app)

SAMPLE_ANALYSIS_DICT = {
    "topic": "Critical SCADA Intrusion",
    "summary": "APT-44 breached 4 regional load dispatch centers through zero-day CVE-2026-38910.",
    "key_facts": [
        {
            "fact_id": "fact_1",
            "statement": "4 regional load dispatch centers experienced unauthorized access.",
            "metric_or_date": "4",
            "source_chunk_ids": ["chunk_1"]
        }
    ],
    "entities": [
        {"name": "APT-44", "category": "threat_actor", "source_chunk_ids": ["chunk_1"]}
    ],
    "dates": [
        {"event": "Breach incident", "date_or_time": "2026-08-10", "source_chunk_ids": ["chunk_1"]}
    ],
    "metrics": [
        {"metric": "Exfiltrated Data", "value": "4.8 GB", "context": "Configs", "source_chunk_ids": ["chunk_1"]}
    ],
    "risks": [
        {"risk": "Grid instability", "severity": "Critical", "mitigation": "Isolate IEC-104", "source_chunk_ids": ["chunk_1"]}
    ],
    "recommendations": [
        {"action": "Deploy firmware hotfix KB-2026-08", "priority": "Immediate", "source_chunk_ids": ["chunk_1"]}
    ],
    "important_statements": [
        {"statement": "Telemetry dropped across centers", "source_chunk_ids": ["chunk_1"]}
    ]
}

@pytest.fixture(autouse=True)
def clean_job_manager():
    mgr = get_job_manager()
    mgr.clear()
    yield
    mgr.clear()

def test_job_creation_returns_processing():
    """Requirement (a): Verify POST /api/ai/analyze immediately returns job_id and status 'processing'."""
    with patch("app.services.ollama_service.OllamaAIService.analyze_source", new_callable=AsyncMock) as mock_analyze:
        # Simulate a long running call that does not complete immediately
        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(10)
            return StructuredContentModel(**SAMPLE_ANALYSIS_DICT)

        mock_analyze.side_effect = slow_analyze

        response = client.post(
            "/api/ai/analyze",
            json={"source_text": "National critical infrastructure SCADA telemetry report exceeding ten characters."}
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"].startswith("job_")
        assert data["status"] == "processing"

def test_job_processing_status_endpoint():
    """Requirement (b): Verify GET /api/ai/analyze/status/{job_id} returns status 'processing' while in progress."""
    mgr = get_job_manager()
    job_id = mgr.create_job()

    response = client.get(f"/api/ai/analyze/status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "processing"

def test_job_completed_status_endpoint():
    """Requirement (c): Verify GET /api/ai/analyze/status/{job_id} returns status 'completed' and canonical result."""
    mgr = get_job_manager()
    job_id = mgr.create_job()
    model = StructuredContentModel(**SAMPLE_ANALYSIS_DICT)
    mgr.set_completed(job_id, model)

    response = client.get(f"/api/ai/analyze/status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert "result" in data
    assert data["result"]["topic"] == "Critical SCADA Intrusion"
    # Also verify canonical fields exist at root for universal compatibility
    assert data["topic"] == "Critical SCADA Intrusion"
    assert len(data["key_facts"]) == 1
    assert data["key_facts"][0]["statement"].startswith("4 regional load")

def test_job_failed_status_endpoint():
    """Requirement (d): Verify GET /api/ai/analyze/status/{job_id} returns status 'failed' with error detail."""
    mgr = get_job_manager()
    job_id = mgr.create_job()
    mgr.set_failed(job_id, "Ollama connection error: Connection refused")

    response = client.get(f"/api/ai/analyze/status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "failed"
    assert "error" in data
    assert "Connection refused" in data["error"]

def test_job_status_not_found():
    """Verify GET /api/ai/analyze/status/{job_id} returns 404 for unknown job_id."""
    response = client.get("/api/ai/analyze/status/non_existent_job_123")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_job_input_validation():
    """Verify POST /api/ai/analyze rejects invalid/empty source text with HTTP 400."""
    response = client.post("/api/ai/analyze", json={"source_text": "short"})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_full_async_job_lifecycle():
    """Verify complete end-to-end lifecycle: submit -> run in background -> retrieve completed status."""
    model = StructuredContentModel(**SAMPLE_ANALYSIS_DICT)

    with patch("app.services.ollama_service.OllamaAIService.analyze_source", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = model

        # 1. Dispatch job
        create_resp = client.post(
            "/api/ai/analyze",
            json={"source_text": "Authorized national cyber incident dossier for full lifecycle verification."}
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        # Give asyncio background task a moment to execute
        await asyncio.sleep(0.05)

        # 2. Poll status endpoint
        status_resp = client.get(f"/api/ai/analyze/status/{job_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "completed"
        assert data["result"]["topic"] == "Critical SCADA Intrusion"
