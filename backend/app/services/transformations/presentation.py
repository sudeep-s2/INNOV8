import json
import logging
import re
from typing import Optional, Dict, Any, Set
from pydantic import ValidationError

from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig
from app.models.outputs import PresentationOutline, PresentationSlide, OutputSourceReference
from app.services.base import (
    AIServiceValidationError,
)
from app.services.ollama_service import OllamaAIService
from app.services import get_ai_service
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.presentation import (
    build_presentation_prompt,
    build_corrective_presentation_prompt
)
from app.services.transformations.base import BaseTransformationService

logger = logging.getLogger(__name__)

class PresentationGenerator(BaseTransformationService[PresentationOutline]):
    """Transforms a canonical StructuredContentModel into a slide-by-slide PresentationOutline."""

    def __init__(self, ai_service: Optional[OllamaAIService] = None):
        self.ai_service = ai_service or OllamaAIService()

    def _clean_json_string(self, raw_text: str) -> str:
        """Extracts JSON string if wrapped in markdown code blocks."""
        clean = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _normalize_presentation_data(
        self,
        data: Dict[str, Any],
        structured_model: StructuredContentModel
    ) -> Dict[str, Any]:
        """Ensures all required fields and slide arrays conform to PresentationOutline schema."""
        default_chunk_id = structured_model.source_chunks[0].chunk_id if structured_model.source_chunks else "chunk_1"

        if not data.get("presentation_title"):
            data["presentation_title"] = f"Briefing: {structured_model.topic}"

        # Normalize slides
        raw_slides = data.get("slides", [])
        norm_slides = []
        if isinstance(raw_slides, list):
            for idx, s in enumerate(raw_slides, 1):
                if isinstance(s, dict):
                    slide_num = s.get("slide_number") or idx
                    title = s.get("title") or f"Slide {idx}: {structured_model.topic}"
                    raw_points = s.get("key_points", [])
                    if isinstance(raw_points, str):
                        raw_points = [raw_points]
                    elif not isinstance(raw_points, list):
                        raw_points = [structured_model.summary]
                    key_points = [str(p).strip() for p in raw_points if str(p).strip()]
                    if not key_points and structured_model.key_facts:
                        key_points = [f.statement for f in structured_model.key_facts[:2]]

                    speaker_notes = s.get("speaker_notes") or f"Presenter guidance for {title}."
                    data_highlights = s.get("data_highlights")

                    # Slide references
                    slide_refs = []
                    raw_s_refs = s.get("source_references", [])
                    if isinstance(raw_s_refs, list):
                        for r in raw_s_refs:
                            if isinstance(r, dict) and r.get("claim"):
                                cid = r.get("source_chunk_id") or default_chunk_id
                                slide_refs.append({
                                    "claim": r["claim"],
                                    "source_chunk_id": str(cid).strip(),
                                    "source_snippet": r.get("source_snippet")
                                })
                    if not slide_refs and key_points:
                        slide_refs.append({
                            "claim": key_points[0],
                            "source_chunk_id": default_chunk_id,
                            "source_snippet": None
                        })

                    norm_slides.append({
                        "slide_number": int(slide_num) if int(slide_num) >= 1 else idx,
                        "title": title,
                        "key_points": key_points,
                        "data_highlights": data_highlights,
                        "speaker_notes": speaker_notes,
                        "source_references": slide_refs
                    })

        # Fallback slides if none generated
        if not norm_slides:
            norm_slides.append({
                "slide_number": 1,
                "title": f"Overview: {structured_model.topic}",
                "key_points": [f.statement for f in structured_model.key_facts[:2]] if structured_model.key_facts else [structured_model.summary],
                "data_highlights": f"{structured_model.metrics[0].metric}: {structured_model.metrics[0].value}" if structured_model.metrics else None,
                "speaker_notes": structured_model.summary,
                "source_references": [{
                    "claim": structured_model.summary[:80],
                    "source_chunk_id": default_chunk_id,
                    "source_snippet": None
                }]
            })
        data["slides"] = norm_slides

        # Normalize root source_references
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
        if not norm_refs:
            norm_refs.append({
                "claim": f"Presentation on {structured_model.topic}",
                "source_chunk_id": default_chunk_id,
                "source_snippet": None
            })
        data["source_references"] = norm_refs

        return data

    def _parse_and_validate_payload(
        self,
        raw_text: str,
        structured_model: StructuredContentModel
    ) -> PresentationOutline:
        """Parses cleaned JSON text, validates schema, and verifies deterministic source grounding."""
        clean_text = self._clean_json_string(raw_text)
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON syntax in presentation response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Presentation response root must be a JSON dictionary object.")

        normalized_data = self._normalize_presentation_data(data, structured_model)

        try:
            presentation = PresentationOutline.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Presentation schema validation error: {str(e)}") from e

        # Grounding Assertion
        valid_chunk_ids = {c.chunk_id for c in structured_model.source_chunks}
        if valid_chunk_ids:
            GroundingValidator.assert_presentation_grounding(presentation, valid_chunk_ids)

        return presentation

    async def transform(
        self,
        structured_model: StructuredContentModel,
        config: TransformationConfig
    ) -> PresentationOutline:
        """Transforms canonical StructuredContentModel into a verified PresentationOutline using Ollama."""
        initial_prompt = build_presentation_prompt(structured_model, config)
        raw_response = await self.ai_service._call_ollama_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, structured_model)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Presentation output failed validation/grounding: {validation_error_msg}. Attempting single corrective retry."
            )

        # Corrective healing retry
        corrective_prompt = build_corrective_presentation_prompt(
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
                f"Presentation generation failed validation after corrective retry: {final_err}"
            ) from final_err
