from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
import httpx
from app.config import settings

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    service: str
    ollama_status: Optional[str] = None
    model: Optional[str] = None
    fallback_available: Optional[bool] = None

class ReadyResponse(BaseModel):
    ready: bool
    service: str
    ollama_online: bool
    model: str
    fallback_configured: bool
    active_provider: str

@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def health_check():
    """Returns basic service status and AI availability flags."""
    return HealthResponse(
        status="ok",
        service="info2impact",
        ollama_status="online",
        model=settings.OLLAMA_MODEL,
        fallback_available=bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
    )

@router.get("/ready", response_model=ReadyResponse, summary="Service Readiness Probe")
async def readiness_probe():
    """Detailed readiness probe checking Ollama connectivity and fallback readiness."""
    ollama_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if res.status_code == 200:
                ollama_online = True
    except Exception:
        ollama_online = False

    fallback_ok = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())

    # Ready if Ollama is online OR fallback is configured
    is_ready = ollama_online or fallback_ok

    return ReadyResponse(
        ready=is_ready,
        service="info2impact",
        ollama_online=ollama_online,
        model=settings.OLLAMA_MODEL,
        fallback_configured=fallback_ok,
        active_provider="ollama" if ollama_online else ("groq" if fallback_ok else "none")
    )
