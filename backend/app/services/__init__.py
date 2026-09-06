from app.services.base import (
    BaseAIService,
    AIServiceError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError
)
from app.services.ollama_service import OllamaAIService

def get_ai_service() -> BaseAIService:
    """Factory function returning the default configured AI service implementation."""
    return OllamaAIService()

__all__ = [
    "BaseAIService",
    "OllamaAIService",
    "AIServiceError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelError",
    "AIServiceValidationError",
    "get_ai_service"
]
