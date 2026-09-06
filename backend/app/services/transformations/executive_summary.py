import json
import logging
import re
from typing import Optional, Dict, Any, Set
from pydantic import ValidationError

from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig
from app.models.outputs import ExecutiveSummary, OutputSourceReference
from app.services.base import (
    AIServiceValidationError,
)
from app.services.ollama_service import OllamaAIService
from app.services import get_ai_service
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.executive_summary import (
    build_executive_summary_prompt,
    build_corrective_executive_summary_prompt
)
from app.services.transformations.base import BaseTransformationService

logger = logging.getLogger(__name__)

class ExecutiveSummaryGenerator(BaseTransformationService[ExecutiveSummary]):
    """Transforms a canonical StructuredContentModel into a decision-ready ExecutiveSummary."""

    def __init__(self, ai_service: Optional[OllamaAIService] = None):
        self.ai_service = ai_service or OllamaAIService()

    def _clean_json_string(self, raw_text: str) -> str:
        """Extracts JSON string if wrapped in markdown code blocks."""
        clean = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _normalize_executive_summary_data(
        self,
        data: Dict[str, Any],
        structured_model: StructuredContentModel
    ) -> Dict[str, Any]:
        """Ensures all required fields and arrays conform to ExecutiveSummary schema."""
        default_chunk_id = structured_model.source_chunks[0].chunk_id if structured_model.source_chunks else "chunk_1"

        if not data.get("title"):
            data["title"] = f"Executive Summary: {structured_model.topic}"
        if not data.get("overview"):
            data["overview"] = structured_model.summary

        # Normalize key_findings
        raw_findings = data.get("key_findings", [])
        if isinstance(raw_findings, str):
            raw_findings = [raw_findings]
        elif not isinstance(raw_findings, list):
            raw_findings = [f.statement for f in structured_model.key_facts[:3]]
        data["key_findings"] = [str(f).strip() for f in raw_findings if str(f).strip()]
        if not data["key_findings"] and structured_model.key_facts:
            data["key_findings"] = [f.statement for f in structured_model.key_facts[:3]]

        # Normalize important_metrics_facts
        raw_metrics = data.get("important_metrics_facts", [])
        if isinstance(raw_metrics, str):
            raw_metrics = [raw_metrics]
        elif not isinstance(raw_metrics, list):
            raw_metrics = [f"{m.metric}: {m.value}" for m in structured_model.metrics[:3]]
        data["important_metrics_facts"] = [str(m).strip() for m in raw_metrics if str(m).strip()]
        if not data["important_metrics_facts"] and structured_model.metrics:
            data["important_metrics_facts"] = [f"{m.metric}: {m.value}" for m in structured_model.metrics[:3]]

        # Normalize risks_implications
        raw_risks = data.get("risks_implications", [])
        if isinstance(raw_risks, str):
            raw_risks = [raw_risks]
        elif not isinstance(raw_risks, list):
            raw_risks = [r.risk for r in structured_model.risks[:3]]
        data["risks_implications"] = [str(r).strip() for r in raw_risks if str(r).strip()]
        if not data["risks_implications"] and structured_model.risks:
            data["risks_implications"] = [r.risk for r in structured_model.risks[:3]]

        # Normalize recommended_actions
        raw_actions = data.get("recommended_actions", [])
        if isinstance(raw_actions, str):
            raw_actions = [raw_actions]
        elif not isinstance(raw_actions, list):
            raw_actions = [rec.action for rec in structured_model.recommendations[:3]]
        data["recommended_actions"] = [str(a).strip() for a in raw_actions if str(a).strip()]
        if not data["recommended_actions"] and structured_model.recommendations:
            data["recommended_actions"] = [rec.action for rec in structured_model.recommendations[:3]]

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
        
        # If model returned no references, create at least one from first finding
        if not norm_refs and data["key_findings"]:
            norm_refs.append({
                "claim": data["key_findings"][0],
                "source_chunk_id": default_chunk_id,
                "source_snippet": None
            })
        data["source_references"] = norm_refs

        return data

    def _parse_and_validate_payload(
        self,
        raw_text: str,
        structured_model: StructuredContentModel
    ) -> ExecutiveSummary:
        """Parses cleaned JSON text, validates schema, and verifies deterministic source grounding."""
        clean_text = self._clean_json_string(raw_text)
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON syntax in executive summary response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Executive summary response root must be a JSON dictionary object.")

        normalized_data = self._normalize_executive_summary_data(data, structured_model)

        try:
            summary = ExecutiveSummary.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Executive summary schema validation error: {str(e)}") from e

        # Grounding Assertion
        valid_chunk_ids = {c.chunk_id for c in structured_model.source_chunks}
        if valid_chunk_ids:
            GroundingValidator.assert_executive_summary_grounding(summary, valid_chunk_ids)

        return summary

    async def transform(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig
    ) -> ExecutiveSummary:
        """Transforms canonical StructuredContentModel into a verified ExecutiveSummary using Ollama."""
        initial_prompt = build_executive_summary_prompt(structured_model, config)
        raw_response = await self.ai_service._call_ollama_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, structured_model)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Executive Summary output failed validation/grounding: {validation_error_msg}. Attempting single corrective retry."
            )

        # Corrective healing retry
        corrective_prompt = build_corrective_executive_summary_prompt(
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
                f"Executive summary generation failed validation after corrective retry: {final_err}"
            ) from final_err
