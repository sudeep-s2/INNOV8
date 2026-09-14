import json
import logging
import re
from typing import List, Optional, Dict, Any, Set
import httpx
from pydantic import ValidationError

from app.config import settings
from app.models.source import SourceChunk
from app.models.content_model import (
    StructuredContentModel,
    KeyFact,
    Entity,
    EventDate,
    MetricNumber,
    RiskImplication,
    RecommendationAction,
    ImportantStatement,
)
from app.services.base import (
    BaseAIService,
    AIServiceError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError,
)
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.analysis import build_analysis_prompt, build_corrective_prompt

logger = logging.getLogger(__name__)

class GroqAIService(BaseAIService):
    """
    Backup AI Service implementation connecting to Groq Cloud API.
    Used as an automatic fallback when local Ollama is offline or experiences timeouts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.base_url = (base_url or settings.GROQ_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.GROQ_TIMEOUT

    def is_available(self) -> bool:
        """Returns True if Groq API key is present and configured."""
        return bool(self.api_key and self.api_key.strip())

    async def _call_api(self, prompt: str) -> str:
        """Sends an async chat completion request to Groq Cloud API."""
        if not self.is_available():
            raise AIServiceError("Groq API key is not configured. Cannot execute fallback request.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are Info2Impact Canonical Analysis Engine. Extract factual structured information with accurate source grounding citations and return strictly valid JSON conforming to the schema.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Groq API: {str(e)}") from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Groq API request timed out after {self.timeout} seconds.") from e
        except httpx.HTTPError as e:
            raise OllamaConnectionError(f"HTTP error communicating with Groq API: {str(e)}") from e

        if response.status_code != 200:
            error_body = response.text
            raise OllamaModelError(f"Groq API returned error HTTP {response.status_code}: {error_body}")

        try:
            res_json = response.json()
            raw_content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not raw_content:
                raise OllamaModelError("Groq API response content was empty.")
            return raw_content
        except Exception as e:
            raise OllamaModelError(f"Failed to parse Groq response envelope: {str(e)}") from e

    async def _call_ollama_api(self, prompt: str) -> str:
        """Alias for _call_api to allow seamless drop-in with existing generators."""
        return await self._call_api(prompt)

    def _clean_json_string(self, raw_text: str) -> str:
        """Extracts JSON string if wrapped in markdown code blocks."""
        clean = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
        return clean

    def _filter_valid_chunk_ids(self, chunk_ids: Any, valid_chunk_ids: Set[str], default_chunk_id: str) -> List[str]:
        """Ensures chunk_ids is a list of strings."""
        if isinstance(chunk_ids, str):
            chunk_ids = [chunk_ids]
        elif not isinstance(chunk_ids, list):
            return [default_chunk_id]

        cleaned = [str(c).strip() for c in chunk_ids if str(c).strip()]
        return cleaned if cleaned else [default_chunk_id]

    def _normalize_structured_data(
        self,
        data: Dict[str, Any],
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> Dict[str, Any]:
        """Ensures all required fields and arrays conform to StructuredContentModel schema."""
        default_chunk_id = chunks[0].chunk_id if chunks else "chunk_1"
        valid_chunk_ids = {c.chunk_id for c in chunks} if chunks else {default_chunk_id}

        if not data.get("topic"):
            data["topic"] = "Analyzed Source Content"
        if not data.get("summary"):
            data["summary"] = source_text[:250].strip() + ("..." if len(source_text) > 250 else "")

        # Key Facts
        raw_facts = data.get("key_facts", [])
        norm_facts = []
        for i, f in enumerate(raw_facts):
            if isinstance(f, str):
                norm_facts.append({
                    "fact_id": f"fact_{i+1}",
                    "statement": f,
                    "source_chunk_ids": [default_chunk_id]
                })
            elif isinstance(f, dict) and f.get("statement"):
                if not f.get("fact_id"):
                    f["fact_id"] = f"fact_{i+1}"
                cids = f.get("source_chunk_ids")
                f["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_facts.append(f)
        data["key_facts"] = norm_facts

        # Entities
        raw_entities = data.get("entities", [])
        norm_entities = []
        for e in raw_entities:
            if isinstance(e, str):
                norm_entities.append({"name": e, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(e, dict) and e.get("name"):
                cids = e.get("source_chunk_ids")
                e["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_entities.append(e)
        data["entities"] = norm_entities

        # Dates
        raw_dates = data.get("dates", [])
        norm_dates = []
        for d in raw_dates:
            if isinstance(d, str):
                norm_dates.append({"event": d, "date_or_time": "Specified in text", "source_chunk_ids": [default_chunk_id]})
            elif isinstance(d, dict) and d.get("event"):
                cids = d.get("source_chunk_ids")
                d["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_dates.append(d)
        data["dates"] = norm_dates

        # Metrics
        raw_metrics = data.get("metrics", [])
        norm_metrics = []
        for m in raw_metrics:
            if isinstance(m, str):
                norm_metrics.append({"metric": m, "value": "Refer to text", "source_chunk_ids": [default_chunk_id]})
            elif isinstance(m, dict) and m.get("metric"):
                cids = m.get("source_chunk_ids")
                m["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_metrics.append(m)
        data["metrics"] = norm_metrics

        # Risks
        raw_risks = data.get("risks", [])
        norm_risks = []
        for r in raw_risks:
            if isinstance(r, str):
                norm_risks.append({"risk": r, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(r, dict) and r.get("risk"):
                cids = r.get("source_chunk_ids")
                r["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_risks.append(r)
        data["risks"] = norm_risks

        # Recommendations
        raw_recs = data.get("recommendations", [])
        norm_recs = []
        for rec in raw_recs:
            if isinstance(rec, str):
                norm_recs.append({"action": rec, "priority": "Standard", "source_chunk_ids": [default_chunk_id]})
            elif isinstance(rec, dict) and rec.get("action"):
                cids = rec.get("source_chunk_ids")
                rec["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_recs.append(rec)
        data["recommendations"] = norm_recs

        # Important Statements
        raw_stmts = data.get("important_statements", [])
        norm_stmts = []
        for s in raw_stmts:
            if isinstance(s, str):
                norm_stmts.append({"statement": s, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(s, dict) and s.get("statement"):
                cids = s.get("source_chunk_ids")
                s["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_stmts.append(s)
        data["important_statements"] = norm_stmts

        # Source Chunks
        if chunks:
            data["source_chunks"] = [c.model_dump() for c in chunks]
        elif "source_chunks" not in data or not data["source_chunks"]:
            data["source_chunks"] = [
                SourceChunk(chunk_id="chunk_1", text=source_text).model_dump()
            ]

        return data

    def _parse_and_validate_payload(
        self,
        raw_text: str,
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> StructuredContentModel:
        """Parses cleaned JSON text, validates schema, and verifies deterministic source grounding."""
        clean_text = self._clean_json_string(raw_text)
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON syntax in Groq response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Model response root must be a JSON dictionary object.")

        normalized_data = self._normalize_structured_data(data, source_text, chunks)

        try:
            model = StructuredContentModel.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Schema validation error from Groq response: {str(e)}") from e

        GroundingValidator.assert_grounding(model)
        return model

    async def analyze_source(
        self,
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> StructuredContentModel:
        """Executes single-pass factual analysis of source text using Groq Cloud API."""
        clean_source = source_text.strip()
        if not clean_source or len(clean_source) < 5:
            raise ValueError("Source text cannot be empty (minimum 5 characters required).")

        initial_prompt = build_analysis_prompt(clean_source, chunks)
        raw_response = await self._call_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, clean_source, chunks)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Groq analysis output failed validation: {validation_error_msg}. Retrying once."
            )

        corrective_prompt = build_corrective_prompt(
            clean_source,
            chunks,
            raw_response,
            validation_error_msg
        )
        retry_response = await self._call_api(corrective_prompt)

        try:
            return self._parse_and_validate_payload(retry_response, clean_source, chunks)
        except (ValueError, GroundingValidationError) as final_err:
            raise AIServiceValidationError(
                f"Groq canonical analysis failed validation after retry: {final_err}"
            ) from final_err
