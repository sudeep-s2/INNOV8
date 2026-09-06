from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig

T = TypeVar("T")

class BaseTransformationService(ABC, Generic[T]):
    """Abstract base class for all output transformation generators."""

    @abstractmethod
    async def transform(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig
    ) -> T:
        """Transforms a canonical StructuredContentModel into a specific output artefact."""
        pass
