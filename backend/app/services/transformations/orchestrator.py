import logging
from typing import List, Optional, Any
from app.models.content_model import StructuredContentModel
from app.models.transformation import (
    TransformationConfig,
    OutputType,
    MultiTransformResponse
)
from app.services.transformations.executive_summary import ExecutiveSummaryGenerator
from app.services.transformations.advisory_brief import AdvisoryBriefGenerator
from app.services.transformations.public_communication import PublicCommunicationGenerator
from app.services.transformations.presentation import PresentationGenerator
from app.services.ollama_service import OllamaAIService

from app.services import get_ai_service

logger = logging.getLogger(__name__)

class TransformationOrchestrator:
    """Orchestrates multi-output transformations from a single canonical StructuredContentModel."""

    def __init__(
        self,
        ai_service: Optional[Any] = None,
        exec_generator: Optional[ExecutiveSummaryGenerator] = None,
        advisory_generator: Optional[AdvisoryBriefGenerator] = None,
        public_comm_generator: Optional[PublicCommunicationGenerator] = None,
        presentation_generator: Optional[PresentationGenerator] = None
    ):
        shared_ai = ai_service or get_ai_service()
        self.exec_generator = exec_generator or ExecutiveSummaryGenerator(ai_service=shared_ai)
        self.advisory_generator = advisory_generator or AdvisoryBriefGenerator(ai_service=shared_ai)
        self.public_comm_generator = public_comm_generator or PublicCommunicationGenerator(ai_service=shared_ai)
        self.presentation_generator = presentation_generator or PresentationGenerator(ai_service=shared_ai)

    async def transform_multi(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig,
        output_types: List[OutputType]
    ) -> MultiTransformResponse:
        """Executes selected transformation generators sequentially/independently against the shared canonical model."""
        response = MultiTransformResponse(topic=structured_model.topic)

        # De-duplicate requested outputs while preserving order
        unique_types = list(dict.fromkeys(output_types))

        for out_type in unique_types:
            key_name = out_type.value if hasattr(out_type, "value") else str(out_type)
            try:
                if out_type == OutputType.executive_summary:
                    response.executive_summary = await self.exec_generator.transform(
                        structured_model=structured_model,
                        config=config
                    )
                elif out_type == OutputType.advisory_brief:
                    response.advisory_brief = await self.advisory_generator.transform(
                        structured_model=structured_model,
                        config=config
                    )
                elif out_type == OutputType.public_communication:
                    response.public_communication = await self.public_comm_generator.transform(
                        structured_model=structured_model,
                        config=config
                    )
                elif out_type == OutputType.presentation:
                    response.presentation = await self.presentation_generator.transform(
                        structured_model=structured_model,
                        config=config
                    )
                else:
                    response.errors[key_name] = f"Unsupported output type: {out_type}"
            except Exception as e:
                logger.error(f"Failed transformation for '{key_name}': {str(e)}", exc_info=True)
                response.errors[key_name] = str(e)

        return response
