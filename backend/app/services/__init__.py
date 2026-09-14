from app.services.base import (
    BaseAIService,
    AIServiceError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError
)
from app.services.ollama_service import OllamaAIService
from app.services.groq_service import GroqAIService
from app.services.fallback_service import FallbackAIService
from app.config import settings

def get_ai_service() -> BaseAIService:
    """Factory function returning the resilient configured AI service implementation."""
    primary = OllamaAIService()
    if settings.GROQ_API_KEY:
        fallback = GroqAIService()
        return FallbackAIService(primary=primary, fallback=fallback)
    return primary

__all__ = [
    "BaseAIService",
    "OllamaAIService",
    "GroqAIService",
    "FallbackAIService",
    "AIServiceError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelError",
    "AIServiceValidationError",
    "get_ai_service"
]
