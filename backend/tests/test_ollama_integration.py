import pytest
import httpx
from app.config import settings
from app.parsers.document_parser import DocumentParser
from app.services.ollama_service import OllamaAIService
from app.models.content_model import StructuredContentModel
from app.validators.grounding import GroundingValidator

def is_ollama_qwen_available() -> bool:
    """Checks whether local Ollama is reachable and has the target model loaded."""
    try:
        res = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if res.status_code == 200:
            models = [m.get("name", "") for m in res.json().get("models", [])]
            return any(settings.OLLAMA_MODEL in m for m in models)
    except Exception:
        pass
    return False

@pytest.mark.asyncio
async def test_live_ollama_qwen3_grounded_canonical_analysis():
    """Live integration test: Ingest synthetic technical dossier -> Chunk -> Ollama Qwen3 -> Validated Grounded Model."""
    if not is_ollama_qwen_available():
        pytest.skip(f"Ollama server or model '{settings.OLLAMA_MODEL}' not available locally. Skipping live integration test.")

    synthetic_dossier = (
        "NATIONAL CRITICAL INFRASTRUCTURE ADVISORY\n"
        "Date: 2026-08-14\n\n"
        "SECTION 1: INCIDENT TELEMETRY\n"
        "Apex Automation sensors detected unauthorized access attempts targeting 4 regional load dispatch centers.\n"
        "The threat actor, tracked as APT-44, exploited an unpatched zero-day vulnerability in SCADA gateways (CVE-2026-38910, CVSS 9.8).\n"
        "Approximately 4.8 Gigabytes of routing configuration files were exfiltrated.\n\n"
        "SECTION 2: THREAT MITIGATION DIRECTIVES\n"
        "Grid security authorities recommend isolating all SCADA IEC-104 ports (TCP 2404) immediately.\n"
        "Operators must deploy emergency firmware hotfix KB-2026-08 across all gateway controllers within 24 hours."
    )

    # 1. Ingestion & Semantic Chunking
    parser = DocumentParser()
    sanitized_text, chunks = parser.parse_text(synthetic_dossier)
    assert len(chunks) >= 2
    valid_chunk_ids = {c.chunk_id for c in chunks}

    # 2. Canonical Analysis with Local Qwen3 8B
    service = OllamaAIService(timeout=180.0)
    model = await service.analyze_source(source_text=sanitized_text, chunks=chunks)

    # 3. Model Integrity & Validation
    assert isinstance(model, StructuredContentModel)
    assert len(model.topic) > 0
    assert len(model.summary) > 0
    assert len(model.source_chunks) == len(chunks)

    # 4. Grounding Validation Check
    is_valid, errors = GroundingValidator.validate_model_grounding(model)
    assert is_valid is True, f"Grounding validation failed: {errors}"

    # Verify extracted items cite existing chunk IDs
    for fact in model.key_facts:
        for cid in fact.source_chunk_ids:
            assert cid in valid_chunk_ids

    for entity in model.entities:
        for cid in entity.source_chunk_ids:
            assert cid in valid_chunk_ids
