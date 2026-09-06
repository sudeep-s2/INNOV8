from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.source import SourceChunk
from app.models.content_model import StructuredContentModel

class AIServiceError(Exception):
    """Base exception for all AI Service operations."""
    pass

class OllamaConnectionError(AIServiceError):
    """Raised when the Ollama server cannot be reached."""
    pass

class OllamaTimeoutError(AIServiceError):
    """Raised when an Ollama request times out."""
    pass

class OllamaModelError(AIServiceError):
    """Raised when Ollama returns an operational error (e.g. model not found)."""
    pass

class AIServiceValidationError(AIServiceError):
    """Raised when LLM response fails schema validation even after corrective retry."""
    pass

class BaseAIService(ABC):
    """Abstract interface defining the contract for AI analysis and transformation services."""

    @abstractmethod
    async def analyze_source(
        self,
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> StructuredContentModel:
        """Analyzes authoritative source text and returns a validated StructuredContentModel."""
        pass
