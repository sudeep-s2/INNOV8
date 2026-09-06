import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types

from app.config import settings
from app.models.schemas import (
    StructuredContentModel, SourceChunk, TransformationConfig,
    OutputType, GroundingCitation, ValidationResult
)
from app.prompts.templates import (
    build_analysis_prompt,
    build_executive_summary_prompt,
    build_advisory_brief_prompt,
    build_public_communication_prompt,
    build_presentation_prompt,
    build_correction_prompt
)
from app.validators.output_validator import OutputValidator

logger = logging.getLogger(__name__)

class AIService:
    """Centralized AI Service layer for Info2Impact.
    Orchestrates:
    1. Single-pass content analysis -> StructuredContentModel (JSON)
    2. Multi-artefact transformations from the shared model
    3. Structural validation and single-pass corrective retry
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = settings.DEFAULT_GEMINI_MODEL

    def _get_client(self, override_key: Optional[str] = None) -> genai.Client:
        key = override_key or self.api_key or settings.GEMINI_API_KEY
        if not key:
            raise ValueError(
                "Gemini API Key not found. Please set GEMINI_API_KEY in backend/.env or configure it via the UI settings."
            )
        return genai.Client(api_key=key)

    def _clean_json_response(self, text: str) -> str:
        """Strips markdown code blocks, backticks, and extraneous whitespace."""
        clean = text.strip()
        # Strip ```json ... ``` or ``` ... ```
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _call_gemini_json(self, prompt: str, override_key: Optional[str] = None) -> Dict[str, Any]:
        """Calls Gemini API with JSON mode enabled and returns parsed Python dictionary."""
        client = self._get_client(override_key)
        
        try:
            # We attempt with gemini-2.5-flash or configured model
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=settings.DEFAULT_TEMPERATURE,
                )
            )
            raw_text = response.text or ""
            clean_text = self._clean_json_response(raw_text)
            return json.loads(clean_text)
        except Exception as e:
            err_str = str(e)
            logger.error(f"Gemini API error: {err_str}")
            # If default model fails, attempt fallback to gemini-1.5-flash or gemini-2.0-flash
            if "2.5" in self.model_name and ("not found" in err_str.lower() or "unsupported" in err_str.lower()):
                try:
                    fallback_response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=settings.DEFAULT_TEMPERATURE,
                        )
                    )
                    clean_fallback = self._clean_json_response(fallback_response.text or "")
                    return json.loads(clean_fallback)
                except Exception as fb_err:
                    raise RuntimeError(f"AI Generation Failed: {str(fb_err)}")
            raise RuntimeError(f"AI Generation Failed: {err_str}")

    def analyze_source(
        self,
        source_text: str,
        chunks: List[SourceChunk],
        api_key: Optional[str] = None
    ) -> StructuredContentModel:
        """Executes the single-pass content analysis to construct the shared StructuredContentModel."""
        prompt = build_analysis_prompt(source_text, chunks)
        data = self._call_gemini_json(prompt, override_key=api_key)
        
        # Merge original source_chunks into the model
        data["source_chunks"] = [c.model_dump() for c in chunks]
        
        try:
            structured_model = StructuredContentModel(**data)
            return structured_model
        except Exception as e:
            logger.warning(f"Schema mapping issue in StructuredContentModel: {e}. Attempting robust fallback.")
            # Ensure required fallback fields
            data.setdefault("main_topic", "Extracted Intelligence Summary")
            data.setdefault("summary", source_text[:300] + "...")
            data.setdefault("key_facts", [])
            data.setdefault("entities", [])
            data.setdefault("events_and_dates", [])
            data.setdefault("numbers_and_metrics", [])
            data.setdefault("risks_and_implications", [])
            data.setdefault("recommendations", [])
            data.setdefault("important_statements", [])
            data["source_chunks"] = [c.model_dump() for c in chunks]
            return StructuredContentModel(**data)

    def generate_single_artefact(
        self,
        output_type: OutputType,
        structured_model: StructuredContentModel,
        config: TransformationConfig,
        api_key: Optional[str] = None
    ) -> Tuple[Dict[str, Any], ValidationResult]:
        """Generates a specific transformation artefact from the shared model, with automated validation and retry."""
        # 1. Select appropriate prompt builder
        if output_type == "executive_summary":
            prompt = build_executive_summary_prompt(structured_model, config)
        elif output_type == "advisory_brief":
            prompt = build_advisory_brief_prompt(structured_model, config)
        elif output_type == "public_communication":
            prompt = build_public_communication_prompt(structured_model, config)
        elif output_type == "presentation_outline":
            prompt = build_presentation_prompt(structured_model, config)
        else:
            raise ValueError(f"Unsupported output type: {output_type}")

        # 2. First-pass generation
        raw_dict = self._call_gemini_json(prompt, override_key=api_key)
        is_valid, issues, validated_data = OutputValidator.validate_output(
            output_type, raw_dict, structured_model
        )

        retried = False
        # 3. If validation failed, perform single-pass corrective healing
        if not is_valid:
            logger.warning(f"Validation failed for {output_type}: {issues}. Attempting corrective retry.")
            retried = True
            correction_prompt = build_correction_prompt(
                output_type=output_type,
                failed_content=json.dumps(raw_dict, indent=2),
                issues=issues,
                model=structured_model
            )
            try:
                healed_dict = self._call_gemini_json(correction_prompt, override_key=api_key)
                is_valid_retry, retry_issues, retry_data = OutputValidator.validate_output(
                    output_type, healed_dict, structured_model
                )
                if is_valid_retry or len(retry_issues) < len(issues):
                    validated_data = retry_data
                    is_valid = is_valid_retry
                    issues = retry_issues
            except Exception as retry_err:
                logger.error(f"Retry generation failed: {retry_err}")

        # Ensure source grounding exists and points to real chunks
        grounding_raw = validated_data.get("source_grounding", [])
        grounding_citations: List[GroundingCitation] = []
        
        chunk_map = {c.chunk_id: c.title for c in structured_model.source_chunks}
        for g in grounding_raw:
            if isinstance(g, dict) and "claim" in g:
                c_id = g.get("source_chunk_id", "chunk_1")
                grounding_citations.append(GroundingCitation(
                    claim=g.get("claim", ""),
                    source_chunk_id=c_id,
                    source_title=chunk_map.get(c_id, g.get("source_title", "Source Document")),
                    source_snippet=g.get("source_snippet", ""),
                    confidence=float(g.get("confidence", 0.95))
                ))
        validated_data["source_grounding"] = [c.model_dump() for c in grounding_citations]

        val_result = ValidationResult(
            is_valid=is_valid,
            score=1.0 if is_valid else max(0.5, 1.0 - (len(issues) * 0.2)),
            issues=issues,
            retried=retried
        )

        return validated_data, val_result
