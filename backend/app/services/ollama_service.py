import json
import logging
import re
from typing import List, Optional, Dict, Any, Set
import httpx
from pydantic import ValidationError

from app.config import settings
from app.models.source import SourceChunk
from app.models.content_model import StructuredContentModel
from app.services.base import (
    BaseAIService,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    AIServiceValidationError,
)
from app.validators.grounding import GroundingValidator, GroundingValidationError
from app.prompts.analysis import build_analysis_prompt, build_corrective_prompt

logger = logging.getLogger(__name__)

class OllamaAIService(BaseAIService):
    """Implementation of BaseAIService connecting to local Ollama instance running Qwen3 8B."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT

    async def _call_ollama_api(self, prompt: str) -> str:
        """Sends an async chat completion request to the Ollama endpoint."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are TransformAI Canonical Analysis Engine. Extract factual structured information with accurate source grounding citations and return strictly valid JSON conforming to the schema."},
                {"role": "user", "content": prompt}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1
            },
            "think": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {self.base_url}. Ensure Ollama is running."
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(
                f"Ollama request timed out after {self.timeout} seconds for model '{self.model}'."
            ) from e
        except httpx.HTTPError as e:
            raise OllamaConnectionError(f"HTTP error communicating with Ollama: {str(e)}") from e

        if response.status_code != 200:
            error_body = response.text
            raise OllamaModelError(
                f"Ollama returned error HTTP {response.status_code}: {error_body}"
            )

        try:
            res_json = response.json()
            raw_content = res_json.get("message", {}).get("content", "")
            if not raw_content:
                raise OllamaModelError("Ollama response message content was empty.")
            return raw_content
        except Exception as e:
            raise OllamaModelError(f"Failed to parse Ollama response envelope: {str(e)}") from e

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
        
        # Keep whatever the model provided so the GroundingValidator can catch any hallucinated chunk IDs
        cleaned = [str(c).strip() for c in chunk_ids if str(c).strip()]
        return cleaned if cleaned else [default_chunk_id]

    def _normalize_structured_data(self, data: Dict[str, Any], source_text: str, chunks: Optional[List[SourceChunk]]) -> Dict[str, Any]:
        """Normalizes and ensures schema conformity for lists and nested items."""
        default_chunk_id = chunks[0].chunk_id if chunks else "chunk_1"
        valid_chunk_ids = {c.chunk_id for c in chunks} if chunks else {default_chunk_id}

        # Topic & Summary
        if not data.get("topic"):
            data["topic"] = "Authoritative Source Analysis"
        if not data.get("summary"):
            data["summary"] = source_text[:200] + "..." if len(source_text) > 200 else source_text

        # Key Facts
        raw_facts = data.get("key_facts", [])
        norm_facts = []
        for idx, f in enumerate(raw_facts, 1):
            if isinstance(f, str):
                norm_facts.append({"fact_id": f"fact_{idx}", "statement": f, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(f, dict) and f.get("statement"):
                f.setdefault("fact_id", f"fact_{idx}")
                cids = f.get("source_chunk_ids")
                f["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_facts.append(f)
        data["key_facts"] = norm_facts

        # Entities
        raw_entities = data.get("entities", [])
        norm_entities = []
        for e in raw_entities:
            if isinstance(e, str):
                norm_entities.append({"name": e, "category": "entity", "source_chunk_ids": [default_chunk_id]})
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
                norm_dates.append({"event": "Chronological timeline event", "date_or_time": d, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(d, dict) and (d.get("date_or_time") or d.get("date")):
                d.setdefault("event", "Event")
                d.setdefault("date_or_time", d.get("date") or d.get("date_or_time"))
                cids = d.get("source_chunk_ids")
                d["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_dates.append(d)
        data["dates"] = norm_dates

        # Metrics
        raw_metrics = data.get("metrics", [])
        norm_metrics = []
        for m in raw_metrics:
            if isinstance(m, str):
                norm_metrics.append({"metric": "Key Figure", "value": m, "source_chunk_ids": [default_chunk_id]})
            elif isinstance(m, dict) and (m.get("value") or m.get("metric")):
                m.setdefault("metric", "Metric")
                m.setdefault("value", str(m.get("value", "")))
                cids = m.get("source_chunk_ids")
                m["source_chunk_ids"] = self._filter_valid_chunk_ids(cids, valid_chunk_ids, default_chunk_id)
                norm_metrics.append(m)
        data["metrics"] = norm_metrics

        # Risks
        raw_risks = data.get("risks", [])
        norm_risks = []
        for r in raw_risks:
            if isinstance(r, str):
                norm_risks.append({"risk": r, "severity": "Medium", "source_chunk_ids": [default_chunk_id]})
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
            raise ValueError(f"Invalid JSON syntax in model response: {str(e)}") from e

        if not isinstance(data, dict):
            raise ValueError("Model response root must be a JSON dictionary object.")

        normalized_data = self._normalize_structured_data(data, source_text, chunks)

        try:
            model = StructuredContentModel.model_validate(normalized_data)
        except ValidationError as e:
            raise ValueError(f"Schema validation error: {str(e)}") from e

        # Grounding Assertion
        GroundingValidator.assert_grounding(model)
        return model

    async def analyze_source(
        self,
        source_text: str,
        chunks: Optional[List[SourceChunk]] = None
    ) -> StructuredContentModel:
        """Executes single-pass factual analysis of source text using Ollama and returns validated, grounded model."""
        clean_source = source_text.strip()
        if not clean_source or len(clean_source) < 5:
            raise ValueError("Source text cannot be empty (minimum 5 characters required).")

        # 1. Primary generation pass
        initial_prompt = build_analysis_prompt(clean_source, chunks)
        raw_response = await self._call_ollama_api(initial_prompt)

        validation_error_msg = ""
        try:
            return self._parse_and_validate_payload(raw_response, clean_source, chunks)
        except (ValueError, GroundingValidationError) as parse_err:
            validation_error_msg = str(parse_err)
            logger.warning(
                f"Initial Ollama output failed validation/grounding: {validation_error_msg}. Attempting single corrective retry."
            )

        # 2. At most ONE corrective healing retry
        corrective_prompt = build_corrective_prompt(
            source_text=clean_source,
            previous_output=raw_response,
            error_details=validation_error_msg,
            chunks=chunks
        )

        retry_response = await self._call_ollama_api(corrective_prompt)
        try:
            return self._parse_and_validate_payload(retry_response, clean_source, chunks)
        except (ValueError, GroundingValidationError) as final_err:
            raise AIServiceValidationError(
                f"Ollama Qwen3 response failed StructuredContentModel validation after corrective retry: {final_err}"
            ) from final_err
