import json
import logging
import re
from typing import Optional, Dict, Any, Set
from pydantic import ValidationError

from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig
from app.models.outputs import PublicCommunication, OutputSourceReference
from app.services.base import (
    AIServiceValidationError,
)
from app.services.ollama_service import OllamaAIService
from app.services import get_ai_service
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.public_communication import (
    build_public_communication_prompt,
    build_corrective_public_communication_prompt
)
from app.services.transformations.base import BaseTransformationService

logger = logging.getLogger(__name__)

class PublicCommunicationGenerator(BaseTransformationService[PublicCommunication]):
    """Transforms a canonical StructuredContentModel into an accessible PublicCommunication release."""

    def __init__(self, ai_service: Optional[OllamaAIService] = None):
        self.ai_service = ai_service or OllamaAIService()

    def _clean_json_string(self, raw_text: str) -> str:
        """Extracts JSON string if wrapped in markdown code blocks."""
        clean = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _normalize_public_communication_data(
        self,
        data: Dict[str, Any],
        structured_model: StructuredContentModel
    ) -> Dict[str, Any]:
        """Ensures all required fields conform to PublicCommunication schema."""
        default_chunk_id = structured_model.source_chunks[0].chunk_id if structured_model.source_chunks else "chunk_1"

        if not data.get("headline"):
            data["headline"] = f"Official Update: {structured_model.topic}"
        if not data.get("opening"):
            data["opening"] = structured_model.summary
        if not data.get("core_message"):
            if structured_model.key_facts:
                data["core_message"] = structured_model.key_facts[0].statement
            else:
                data["core_message"] = structured_model.summary
        if not data.get("explanation"):
            data["explanation"] = structured_model.summary
        if not data.get("public_guidance"):
            if structured_model.recommendations:
                data["public_guidance"] = f"Action underway: {structured_model.recommendations[0].action}"
            else:
                data["public_guidance"] = "Authorities are actively monitoring the situation and systems remain under close supervision."

        # Normalize source_references
        raw_refs = data.get("source_references", [])
        norm_refs = []
        if isinstance(raw_refs, list):
            for ref in raw_refs:
                if isinstance(ref, dict) and ref.get("claim"):
                    cid = ref.get("source_chunk_id") or default_chunk_id
                    norm_refs.append({
                        "claim": ref["claim"],
                        "source_chunk_id": str(cid).strip(),
                        "source_snippet": ref.get("source_snippet")
                    })
                elif isinstance(ref, str):
                    norm_refs.append({
                        "claim": ref,
                        "source_chunk_id": default_chunk_id,
                        "source_snippet": None
                    })

        if not norm_refs and data.get("core_message"):
            norm_refs.append({
                "claim": data["core_message"],
                "source_chunk_id": default_chunk_id,
                "source_snippet": None
            })
        data["source_references"] = norm_refs

        return data

    def _parse_and_validate_payload(
        self,
        raw_text: str,
        structured_model: StructuredContentModel
    ) -> PublicCommunication:
        """Parses cleaned JSON text, validates schema, and verifies deterministic source grounding."""
        clean_text = self._clean_json_string(raw_text)
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON syntax in public communication response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Public communication response root must be a JSON dictionary object.")

        normalized_data = self._normalize_public_communication_data(data, structured_model)

        try:
            comm = PublicCommunication.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Public communication schema validation error: {str(e)}") from e

        # Grounding Assertion
        valid_chunk_ids = {c.chunk_id for c in structured_model.source_chunks}
        if valid_chunk_ids:
            GroundingValidator.assert_public_communication_grounding(comm, valid_chunk_ids)

        return comm

    async def transform(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig
    ) -> PublicCommunication:
        """Transforms canonical StructuredContentModel into a verified PublicCommunication using Ollama."""
        initial_prompt = build_public_communication_prompt(structured_model, config)
        raw_response = await self.ai_service._call_ollama_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, structured_model)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Public Communication output failed validation/grounding: {validation_error_msg}. Attempting single corrective retry."
            )

        # Corrective healing retry
        corrective_prompt = build_corrective_public_communication_prompt(
            structured_model=structured_model,
            config=config,
            previous_output=raw_response,
            error_details=validation_error_msg
        )

        retry_response = await self.ai_service._call_ollama_api(corrective_prompt)
        try:
            return self._parse_and_validate_payload(retry_response, structured_model)
        except (ValueError, GroundingValidationError) as final_err:
            raise AIServiceValidationError(
                f"Public communication generation failed validation after corrective retry: {final_err}"
            ) from final_err
