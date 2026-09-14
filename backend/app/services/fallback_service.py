import logging
from typing import List, Optional, Any
from app.config import settings
from app.models.source import SourceChunk
from app.models.content_model import StructuredContentModel
from app.services.base import (
    BaseAIService,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceError,
)
from app.services.ollama_service import OllamaAIService
from app.services.groq_service import GroqAIService

logger = logging.getLogger(__name__)

class FallbackAIService(BaseAIService):
    """
    Resilient composite AI Service.
    Attempts primary AI service (Ollama Qwen3 local) first;
    if connection fails or times out, falls back to Groq Cloud backup.
    """

    def __init__(
        self,
        primary: Optional[BaseAIService] = None,
        fallback: Optional[BaseAIService] = None
    ):
        self.primary = primary or OllamaAIService()
        self.fallback = fallback or GroqAIService()

    async def _call_ollama_api(self, prompt: str) -> str:
        """Attempts primary inference, falling back to Groq if local fails."""
        if settings.AI_PROVIDER.lower() == "groq" and hasattr(self.fallback, "is_available") and self.fallback.is_available():
            logger.info("AI_PROVIDER is configured to 'groq'; executing via Groq Cloud API directly.")
            return await self.fallback._call_api(prompt)

        try:
            return await self.primary._call_ollama_api(prompt)
        except (OllamaConnectionError, OllamaTimeoutError) as err:
            if hasattr(self.fallback, "is_available") and self.fallback.is_available():
                logger.warning(
                    f"Primary Ollama inference failed ({err}). Transparently falling back to Groq Cloud ({settings.GROQ_MODEL})..."
                )
                try:
                    return await self.fallback._call_api(prompt)
                except Exception as fallback_err:
                    logger.error(f"Fallback AI service also failed: {fallback_err}")
                    raise OllamaConnectionError(f"{str(err)} (Fallback error: {str(fallback_err)})") from fallback_err
            raise

    async def analyze_source(
        self,
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> StructuredContentModel:
        """Executes canonical analysis with primary service, falling back to Groq if primary fails."""
        if settings.AI_PROVIDER.lower() == "groq" and hasattr(self.fallback, "is_available") and self.fallback.is_available():
            logger.info("AI_PROVIDER is configured to 'groq'; analyzing with Groq Cloud directly.")
            return await self.fallback.analyze_source(source_text, chunks)

        try:
            return await self.primary.analyze_source(source_text, chunks)
        except (OllamaConnectionError, OllamaTimeoutError) as err:
            if hasattr(self.fallback, "is_available") and self.fallback.is_available():
                logger.warning(
                    f"Primary Ollama analysis failed ({err}). Transparently falling back to Groq Cloud ({settings.GROQ_MODEL})..."
                )
                try:
                    return await self.fallback.analyze_source(source_text, chunks)
                except Exception as fallback_err:
                    logger.error(f"Fallback AI service also failed: {fallback_err}")
                    raise OllamaConnectionError(f"{str(err)} (Fallback error: {str(fallback_err)})") from fallback_err
            raise
