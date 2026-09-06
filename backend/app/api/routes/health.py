from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    service: str

@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def health_check():
    """Returns basic service status to verify backend availability."""
    return HealthResponse(
        status="ok",
        service="info2impact"
    )
