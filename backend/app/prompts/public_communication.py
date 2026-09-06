import json
from app.models.content_model import StructuredContentModel
from app.models.transformation import TransformationConfig

PUBLIC_COMMUNICATION_SYSTEM_INSTRUCTION = """You are the Public Communication Transformation Engine of TransformAI.
Your mission is to transform a Canonical Structured Content Model into clear, accessible, and reassuring public communication for citizens and the general public.

CRITICAL TRANSFORMATION RULES:
1. CANONICAL TRUTH: The provided StructuredContentModel is your single authoritative source of truth.
2. ZERO INVENTION: Do NOT invent facts, casualty numbers, false alarms, speculative timelines, or directives absent from the canonical model.
3. PLAIN LANGUAGE & ACCESSIBILITY: Translate complex technical jargon into clear, informative, and reassuring language suitable for citizens without losing factual integrity.
4. GROUNDING CITATIONS: Key public statements and guidance MUST include source grounding citations in 'source_references' citing ONLY valid SourceChunk IDs from the model.
5. STRUCTURED JSON OUTPUT: Output MUST be a single, valid, complete JSON object conforming strictly to the requested PublicCommunication schema.
6. NO MARKDOWN WRAPPERS: Return raw JSON only with no conversational text or codeblocks.
"""

def build_public_communication_prompt(
    structured_model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    """Builds the transformation prompt instructing Qwen3 to synthesize a PublicCommunication artefact from the canonical model."""
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

    return f"""{PUBLIC_COMMUNICATION_SYSTEM_INSTRUCTION}

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

Synthesize a clear and accessible Public Communication release tailored for {config.audience.value} with an {config.tone.value} tone.
Extract and return ONLY a JSON object conforming to this exact schema:
{{
  "headline": "Clear, engaging, and informative public headline",
  "opening": "Accessible opening paragraph framing the matter for citizens",
  "core_message": "Primary takeaway in direct, accessible, jargon-free plain language",
  "explanation": "Context and significance explained simply without confusing technical jargon",
  "public_guidance": "Actionable advice, reassurance, or status update for the public",
  "source_references": [
    {{
      "claim": "Key claim or statement in the release",
      "source_chunk_id": "chunk_1",
      "source_snippet": "Supporting excerpt or phrase from chunk"
    }}
  ]
}}

Return raw JSON only.
"""

def build_corrective_public_communication_prompt(
    structured_model: StructuredContentModel,
    config: TransformationConfig,
    previous_output: str,
    error_details: str
) -> str:
    """Builds a single-pass corrective prompt if the previous public communication output failed validation or grounding."""
    valid_ids = [c.chunk_id for c in structured_model.source_chunks]
    return f"""{PUBLIC_COMMUNICATION_SYSTEM_INSTRUCTION}

VALIDATION FAILURE:
Your previous public communication transformation failed validation with the following error:
{error_details}

CRITICAL INSTRUCTION:
1. Ensure the JSON structure matches the PublicCommunication schema exactly.
2. Ensure all source_chunk_id values in 'source_references' exist in the valid list: {valid_ids}.
3. Return raw JSON only.

PREVIOUS FAILED OUTPUT:
{previous_output}

Please fix the errors and output a strictly valid, complete JSON object.
"""
