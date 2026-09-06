from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.source import router as source_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.transform import router as transform_router

api_router = APIRouter()

# Mount routes
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(source_router, prefix="/source", tags=["Source Ingestion"])
api_router.include_router(analysis_router, prefix="/ai", tags=["AI Analysis"])
api_router.include_router(transform_router, prefix="/transform", tags=["Transformations"])
