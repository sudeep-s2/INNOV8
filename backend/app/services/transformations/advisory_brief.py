import json
import logging
import re
from typing import Optional, Dict, Any, Set
from pydantic import ValidationError

from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig
from app.models.outputs import AdvisoryBrief, OutputSourceReference
from app.services.base import (
    AIServiceValidationError,
)
from app.services.ollama_service import OllamaAIService
from app.services import get_ai_service
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.advisory_brief import (
    build_advisory_brief_prompt,
    build_corrective_advisory_brief_prompt
)
from app.services.transformations.base import BaseTransformationService

logger = logging.getLogger(__name__)

class AdvisoryBriefGenerator(BaseTransformationService[AdvisoryBrief]):
    """Transforms a canonical StructuredContentModel into a formal, structured AdvisoryBrief."""

    def __init__(self, ai_service: Optional[OllamaAIService] = None):
        self.ai_service = ai_service or OllamaAIService()

    def _clean_json_string(self, raw_text: str) -> str:
        """Extracts JSON string if wrapped in markdown code blocks."""
        clean = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _normalize_advisory_brief_data(
        self,
        data: Dict[str, Any],
        structured_model: StructuredContentModel
    ) -> Dict[str, Any]:
        """Ensures all required fields and arrays conform to AdvisoryBrief schema."""
        default_chunk_id = structured_model.source_chunks[0].chunk_id if structured_model.source_chunks else "chunk_1"

        if not data.get("title"):
            data["title"] = f"ADVISORY BRIEF: {structured_model.topic}"
        if not data.get("situation_context"):
            data["situation_context"] = structured_model.summary

        # Normalize key_observations
        raw_obs = data.get("key_observations", [])
        if isinstance(raw_obs, str):
            raw_obs = [raw_obs]
        elif not isinstance(raw_obs, list):
            raw_obs = [f.statement for f in structured_model.key_facts[:3]]
        data["key_observations"] = [str(o).strip() for o in raw_obs if str(o).strip()]
        if not data["key_observations"] and structured_model.key_facts:
            data["key_observations"] = [f.statement for f in structured_model.key_facts[:3]]

        # Normalize verified_facts
        raw_facts = data.get("verified_facts", [])
        if isinstance(raw_facts, str):
            raw_facts = [raw_facts]
        elif not isinstance(raw_facts, list):
            raw_facts = [f"{m.metric}: {m.value}" for m in structured_model.metrics[:3]]
        data["verified_facts"] = [str(f).strip() for f in raw_facts if str(f).strip()]
        if not data["verified_facts"] and structured_model.metrics:
            data["verified_facts"] = [f"{m.metric}: {m.value}" for m in structured_model.metrics[:3]]
        elif not data["verified_facts"] and structured_model.key_facts:
            data["verified_facts"] = [f.statement for f in structured_model.key_facts[:2]]

        # Normalize risk_impact
        if not data.get("risk_impact"):
            if structured_model.risks:
                data["risk_impact"] = f"{structured_model.risks[0].severity or 'High'}: {structured_model.risks[0].risk}"
            else:
                data["risk_impact"] = "Operational risk assessment pending further field telemetry."

        # Normalize recommended_actions_directives
        raw_directives = data.get("recommended_actions_directives", [])
        if isinstance(raw_directives, str):
            raw_directives = [raw_directives]
        elif not isinstance(raw_directives, list):
            raw_directives = [rec.action for rec in structured_model.recommendations[:3]]
        data["recommended_actions_directives"] = [str(d).strip() for d in raw_directives if str(d).strip()]
        if not data["recommended_actions_directives"] and structured_model.recommendations:
            data["recommended_actions_directives"] = [rec.action for rec in structured_model.recommendations[:3]]

        # Normalize caveats
        raw_caveats = data.get("caveats", [])
        if isinstance(raw_caveats, str):
            raw_caveats = [raw_caveats]
        elif not isinstance(raw_caveats, list):
            raw_caveats = []
        data["caveats"] = [str(c).strip() for c in raw_caveats if str(c).strip()]

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

        if not norm_refs and data["key_observations"]:
            norm_refs.append({
                "claim": data["key_observations"][0],
                "source_chunk_id": default_chunk_id,
                "source_snippet": None
            })
        data["source_references"] = norm_refs

        return data

    def _parse_and_validate_payload(
        self,
        raw_text: str,
        structured_model: StructuredContentModel
    ) -> AdvisoryBrief:
        """Parses cleaned JSON text, validates schema, and verifies deterministic source grounding."""
        clean_text = self._clean_json_string(raw_text)
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON syntax in advisory brief response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Advisory brief response root must be a JSON dictionary object.")

        normalized_data = self._normalize_advisory_brief_data(data, structured_model)

        try:
            advisory = AdvisoryBrief.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Advisory brief schema validation error: {str(e)}") from e

        # Grounding Assertion
        valid_chunk_ids = {c.chunk_id for c in structured_model.source_chunks}
        if valid_chunk_ids:
            GroundingValidator.assert_advisory_brief_grounding(advisory, valid_chunk_ids)

        return advisory

    async def transform(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig
    ) -> AdvisoryBrief:
        """Transforms canonical StructuredContentModel into a verified AdvisoryBrief using Ollama."""
        initial_prompt = build_advisory_brief_prompt(structured_model, config)
        raw_response = await self.ai_service._call_ollama_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, structured_model)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Advisory Brief output failed validation/grounding: {validation_error_msg}. Attempting single corrective retry."
            )

        # Corrective healing retry
        corrective_prompt = build_corrective_advisory_brief_prompt(
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
                f"Advisory brief generation failed validation after corrective retry: {final_err}"
            ) from final_err
