import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description=f"{settings.PROJECT_SLOGAN} — {settings.ORGANIZATION}",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware supporting local development, Vercel frontend, and HTTPS tunnels
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
is_wildcard = "*" in cors_origins or not cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if not is_wildcard else [],
    allow_origin_regex=r"https?://.*" if is_wildcard else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount API router
app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "description": settings.PROJECT_SLOGAN,
        "organization": settings.ORGANIZATION,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
