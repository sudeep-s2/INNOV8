from typing import List, Optional
from app.models.source import SourceChunk

ANALYSIS_SYSTEM_INSTRUCTION = """You are the Canonical Content Analysis Engine of Info2Impact.
Your mission is to perform a strict, single-pass factual extraction of the provided source document.

CRITICAL OPERATIONAL RULES:
1. AUTHORITATIVE TRUTH: Rely strictly and exclusively on the provided source text.
2. ZERO SPECULATION: Do NOT invent, assume, or extrapolate facts, metrics, numbers, dates, entities, or recommendations not explicitly present in the source.
3. GROUNDING CITATIONS: Every extracted item (facts, entities, dates, metrics, risks, recommendations, statements) MUST cite the exact SourceChunk ID(s) (e.g. ["chunk_1"]) that directly substantiate it.
4. VALID CHUNK IDS ONLY: Only cite chunk IDs provided in the prompt (e.g., chunk_1, chunk_2). Never cite non-existent chunk IDs.
5. EMPTY FIELDS IF ABSENT: If the source does not contain an explicit recommendation, risk, or metric, leave that list empty ([]). Do NOT invent recommendations.
6. STRUCTURED CANONICAL JSON: Output MUST be a single, valid, clean JSON object matching the exact schema requested.
7. NO MARKDOWN WRAPPERS: Return raw JSON only without conversational preamble or markdown codeblocks.
"""

def build_analysis_prompt(source_text: str, chunks: Optional[List[SourceChunk]] = None) -> str:
    """Builds the extraction prompt for Qwen3 to produce a valid, source-grounded StructuredContentModel JSON."""
    if chunks:
        chunks_formatted = "\n\n".join(
            [f"[{c.chunk_id}] (Location: {c.source_location or 'General'}):\n{c.text}" for c in chunks]
        )
        available_ids = [c.chunk_id for c in chunks]
        source_presentation = f"AVAILABLE SOURCE CHUNKS:\n{chunks_formatted}\n\nVALID CHUNK IDS TO CITE: {available_ids}"
    else:
        source_presentation = f"SOURCE TEXT:\n[chunk_1]:\n{source_text}\n\nVALID CHUNK IDS TO CITE: ['chunk_1']"

    return f"""{ANALYSIS_SYSTEM_INSTRUCTION}

Analyze the following source material and extract its complete factual and semantic structure with source grounding citations.

{source_presentation}

Extract and return ONLY a JSON object conforming to this exact schema:
{{
  "topic": "Concise definition of the primary subject, domain, or incident described in the source",
  "summary": "Neutral, comprehensive synopsis covering the core facts of the entire document",
  "key_facts": [
    {{
      "fact_id": "fact_1",
      "statement": "Verified factual finding directly stated in the text",
      "metric_or_date": "Any specific number or date associated with this fact (or null)",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "entities": [
    {{
      "name": "Organization, threat group, software system, or key entity name",
      "category": "organization | threat_actor | system | vulnerability | location | patch | other",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "dates": [
    {{
      "event": "Description of incident, milestone, or event",
      "date_or_time": "Exact date, timestamp, or timeline mentioned",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "metrics": [
    {{
      "metric": "Name of indicator or metric (e.g. 'Data Exfiltrated', 'Affected Nodes')",
      "value": "Exact quantitative number, percentage, or currency figure",
      "context": "Contextual description of this metric",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "risks": [
    {{
      "risk": "Description of vulnerability, hazard, threat, or failure mode",
      "severity": "Critical | High | Medium | Low",
      "mitigation": "Stated mitigation strategy if present in text (or null)",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "recommendations": [
    {{
      "action": "Concrete recommended action, directive, or next step explicitly stated in source",
      "priority": "Immediate | High | Medium | Standard",
      "source_chunk_ids": ["chunk_1"]
    }}
  ],
  "important_statements": [
    {{
      "statement": "Key authoritative statement, finding, or policy declaration",
      "source_chunk_ids": ["chunk_1"]
    }}
  ]
}}

Return raw JSON only.
"""

def build_corrective_prompt(source_text: str, previous_output: str, error_details: str, chunks: Optional[List[SourceChunk]] = None) -> str:
    """Builds a single-pass corrective prompt if the previous response failed JSON parsing, schema validation, or grounding verification."""
    valid_ids = [c.chunk_id for c in chunks] if chunks else ["chunk_1"]
    return f"""{ANALYSIS_SYSTEM_INSTRUCTION}

VALIDATION FAILURE:
Your previous output failed validation with the following error:
{error_details}

CRITICAL INSTRUCTION:
Ensure all cited chunk IDs exist within the valid chunk list: {valid_ids}.

PREVIOUS FAILED OUTPUT:
{previous_output}

SOURCE TEXT:
{source_text}

Fix all schema and grounding errors and return a strictly valid, complete JSON object conforming to the required schema. Output raw JSON only.
"""
