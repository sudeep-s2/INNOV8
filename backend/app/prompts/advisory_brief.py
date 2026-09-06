import json
from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig

ADVISORY_BRIEF_SYSTEM_INSTRUCTION = """You are the Advisory Brief Transformation Engine of Info2Impact.
Your mission is to transform a Canonical Structured Content Model into a formal, actionable, and structured Advisory Brief for technical and operational personnel.

CRITICAL TRANSFORMATION RULES:
1. CANONICAL TRUTH: The provided StructuredContentModel is your single authoritative source of truth.
2. ZERO INVENTION: Do NOT invent, assume, or extrapolate technical findings, CVEs, IP addresses, ports, metrics, dates, or directives not present in the canonical model.
3. OPERATIONAL REGISTER: Adapt the language to be technical, precise, risk-bounded, and actionable according to the specified audience, tone, detail level, and objective.
4. GROUNDING CITATIONS: Key observations, verified facts, and directives MUST include source grounding citations in 'source_references' citing ONLY valid SourceChunk IDs from the model.
5. STRUCTURED JSON OUTPUT: Output MUST be a single, valid, complete JSON object conforming strictly to the requested AdvisoryBrief schema.
6. NO MARKDOWN WRAPPERS: Return raw JSON only with no conversational text or codeblocks.
"""

def build_advisory_brief_prompt(
    structured_model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    """Builds the transformation prompt instructing Qwen3 to synthesize an AdvisoryBrief from the canonical model."""
    canonical_data = {
        "topic": structured_model.topic,
        "summary": structured_model.summary,
        "key_facts": [f.model_dump() for f in structured_model.key_facts],
        "entities": [e.model_dump() for e in structured_model.entities],
        "dates": [d.model_dump() for d in structured_model.dates],
        "metrics": [m.model_dump() for m in structured_model.metrics],
        "risks": [r.model_dump() for r in structured_model.risks],
        "recommendations": [rec.model_dump() for rec in structured_model.recommendations],
        "important_statements": [s.model_dump() for s in structured_model.important_statements]
    }

    available_chunk_ids = [c.chunk_id for c in structured_model.source_chunks]
    chunks_context = "\n".join([f"[{c.chunk_id}] (Location: {c.source_location or 'General'}): {c.text[:200]}..." for c in structured_model.source_chunks])

    return f"""{ADVISORY_BRIEF_SYSTEM_INSTRUCTION}

TRANSFORMATION PARAMETERS:
- Target Audience: {config.audience.value}
- Tone: {config.tone.value}
- Level of Detail: {config.detail_level.value}
- Communication Objective: {config.objective.value}
- Output Language: {config.language.value}

CANONICAL STRUCTURED CONTENT MODEL (SOURCE OF TRUTH):
{json.dumps(canonical_data, indent=2)}

AVAILABLE SOURCE CHUNKS FOR GROUNDING CITATIONS:
{chunks_context}
VALID CHUNK IDS: {available_chunk_ids}

Synthesize a formal Advisory Brief tailored for {config.audience.value} with a {config.tone.value} tone.
Extract and return ONLY a JSON object conforming to this exact schema:
{{
  "title": "Formal advisory title and threat descriptor",
  "situation_context": "Operational background and situational context",
  "key_observations": [
    "Specific technical or operational observation 1",
    "Specific technical or operational observation 2"
  ],
  "verified_facts": [
    "Substantiated fact or telemetry point from canonical model"
  ],
  "risk_impact": "Detailed threat exposure, vulnerability analysis, and operational blast radius",
  "recommended_actions_directives": [
    "Mandatory containment, remediation, or operational directive 1",
    "Mandatory directive 2"
  ],
  "caveats": [
    "Operational boundary, assumption, or limitation based strictly on canonical data"
  ],
  "source_references": [
    {{
      "claim": "Key claim or directive from advisory",
      "source_chunk_id": "chunk_1",
      "source_snippet": "Supporting excerpt or phrase from chunk"
    }}
  ]
}}

Return raw JSON only.
"""

def build_corrective_advisory_brief_prompt(
    structured_model: StructuredContentModel,
    config: TransformationConfig,
    previous_output: str,
    error_details: str
) -> str:
    """Builds a single-pass corrective prompt if the previous advisory brief output failed validation or grounding."""
    valid_ids = [c.chunk_id for c in structured_model.source_chunks]
    return f"""{ADVISORY_BRIEF_SYSTEM_INSTRUCTION}

VALIDATION FAILURE:
Your previous advisory brief transformation failed validation with the following error:
{error_details}

CRITICAL INSTRUCTION:
1. Ensure the JSON structure matches the AdvisoryBrief schema exactly.
2. Ensure all source_chunk_id values in 'source_references' exist in the valid list: {valid_ids}.
3. Return raw JSON only.

PREVIOUS FAILED OUTPUT:
{previous_output}

Please fix the errors and output a strictly valid, complete JSON object.
"""
