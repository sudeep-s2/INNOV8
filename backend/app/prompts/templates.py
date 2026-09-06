import json
from typing import Dict, Any, List
from app.models.schemas import TransformationConfig, StructuredContentModel, SourceChunk

SYSTEM_BASE_INSTRUCTION = """You are Info2Impact, an enterprise-grade AI content transformation platform designed for the National Technical Research Organisation (NTRO).
Your core mission is: ONE SOURCE -> STRUCTURED UNDERSTANDING -> MULTIPLE PURPOSE-SPECIFIC TRANSFORMATIONS.

CRITICAL RULES:
1. Grounding & Factual Integrity: The source content is your sole authoritative truth. Do NOT fabricate or extrapolate unstated numbers, events, or facts.
2. Cross-Artefact Consistency: All output claims must align with the structured intermediate representation and source chunks.
3. Output Format: Always respond with clean, valid, unescaped JSON matching the exact schema requested. Do not include markdown code block backticks (like ```json) unless instructed.
"""

def build_analysis_prompt(source_text: str, chunks: List[SourceChunk]) -> str:
    chunks_text = "\n\n".join([f"[{c.chunk_id}] (Title: {c.title}):\n{c.content}" for c in chunks])
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are executing the CONTENT ANALYSIS stage. Analyze the following segmented source document and extract a comprehensive, structured intermediate representation.

SOURCE CHUNKS:
{chunks_text}

Extract and return ONLY a JSON object matching this exact schema:
{{
  "main_topic": "Concise definition of the primary subject, domain, and objective of the source document",
  "summary": "Neutral 3-4 sentence comprehensive synopsis of the entire document",
  "key_facts": [
    {{
      "fact_id": "fact_1",
      "statement": "Clear, verified factual finding directly stated in the text",
      "metric_or_date": "Any specific number, statistic, or date associated (or null)",
      "category": "finding | risk | recommendation | metric | background",
      "source_chunk_id": "chunk_1"
    }}
  ],
  "entities": ["List of key organizations, systems, technologies, locations, or key figures explicitly mentioned"],
  "events_and_dates": [
    {{
      "event": "Description of incident, milestone, or event",
      "date": "Date or timeframe mentioned",
      "source_chunk_id": "chunk_1"
    }}
  ],
  "numbers_and_metrics": [
    {{
      "metric": "Name of metric or indicator (e.g. 'Latency reduction', 'Budget allocation')",
      "value": "Exact number or percentage (e.g. '32%', '$4.5M')",
      "context": "Context of this metric",
      "source_chunk_id": "chunk_1"
    }}
  ],
  "risks_and_implications": [
    {{
      "risk": "Description of hazard, operational threat, vulnerability, or failure mode",
      "impact_level": "High | Medium | Low",
      "mitigation": "Stated or implied mitigation strategy",
      "source_chunk_id": "chunk_1"
    }}
  ],
  "recommendations": [
    {{
      "action": "Concrete recommended action or tactical directive",
      "priority": "Immediate | High | Medium | Standard",
      "target_owner": "Entity or team responsible if mentioned",
      "source_chunk_id": "chunk_1"
    }}
  ],
  "important_statements": [
    {{
      "statement": "Key authoritative statement, finding, or policy declaration",
      "significance": "Why this statement matters",
      "source_chunk_id": "chunk_1"
    }}
  ]
}}

Ensure every key_fact, event, metric, risk, and recommendation cites the exact source_chunk_id where it appears. Output pure JSON only.
"""

def build_executive_summary_prompt(
    model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    model_json = json.dumps(model.model_dump(exclude={"source_chunks"}), indent=2)
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are generating an EXECUTIVE SUMMARY from the structured source analysis below.

TRANSFORMATION CONTROLS:
- Target Audience: {config.target_audience} (Focus on high-level strategic decisions, business/operational impact)
- Tone: {config.tone}
- Level of Detail: {config.level_of_detail}
- Communication Objective: {config.objective}
- Language: {config.language}

STRUCTURED INTERMEDIATE REPRESENTATION:
{model_json}

INSTRUCTIONS:
1. Synthesize the findings into an impactful, decision-oriented Executive Summary.
2. Structure the output into clear sections: Title, Executive Overview, Key Findings (bulleted), Important Facts & Numbers, Risks & Implications, and Recommended Strategic Actions.
3. For every key factual claim, provide a grounding citation referencing the supporting source_chunk_id and a brief source_snippet.
4. Strictly avoid speculation. Every number and finding must be derived from the structured model.

Return ONLY a JSON object matching this schema:
{{
  "title": "Clear, authoritative executive summary title",
  "executive_overview": "High-level strategic synthesis (2-3 paragraphs)",
  "key_findings": [
    "Critical finding 1 with strategic impact",
    "Critical finding 2"
  ],
  "important_facts_and_numbers": [
    "Key statistic or metric with context",
    "Key timeline or resource figure"
  ],
  "risks_or_implications": [
    "Operational, technical, or strategic risk with consequences",
    "Secondary vulnerability or bottleneck"
  ],
  "recommended_actions": [
    "Strategic decision or immediate executive directive",
    "Mid-to-long term initiative"
  ],
  "source_grounding": [
    {{
      "claim": "Specific statement made in this summary",
      "source_chunk_id": "chunk_1",
      "source_title": "Section Title",
      "source_snippet": "Exact phrase from source verifying this",
      "confidence": 0.98
    }}
  ]
}}
"""

def build_advisory_brief_prompt(
    model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    model_json = json.dumps(model.model_dump(exclude={"source_chunks"}), indent=2)
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are generating an ADVISORY BRIEF (Technical / Intelligence / Operational Advisory) from the structured source analysis below.

TRANSFORMATION CONTROLS:
- Target Audience: {config.target_audience}
- Tone: {config.tone} (Rigorous, formal, analytical)
- Level of Detail: {config.level_of_detail}
- Communication Objective: {config.objective}
- Language: {config.language}

STRUCTURED INTERMEDIATE REPRESENTATION:
{model_json}

INSTRUCTIONS:
1. Produce a rigorous, highly structured Advisory Brief formatted for operational leadership, intelligence units, or technical advisors.
2. Sections required: Title, Situation/Context, Key Observations, Relevant Facts & Telemetry, Risk & Impact Assessment, Recommended Actions (tactical + strategic), and Important Caveats / Assumptions.
3. Do NOT invent facts or extrapolate beyond verified data.
4. Include source grounding citations linking key assessments to source_chunk_ids.

Return ONLY a JSON object matching this schema:
{{
  "title": "ADVISORY BRIEF: [Title / Topic Descriptor]",
  "situation_context": "Operational background and situation context paragraph",
  "key_observations": [
    "Direct observation 1",
    "Direct observation 2"
  ],
  "relevant_facts": [
    "Substantiated fact with dates or metrics",
    "Verified technical or organizational fact"
  ],
  "risk_and_impact_assessment": "Comprehensive risk analysis detailing threat exposure, severity, and potential blast radius",
  "recommended_actions": [
    "Immediate containment / mitigation step",
    "Systemic operational enhancement"
  ],
  "important_caveats": [
    "Data limitation or boundary condition",
    "Operational assumption"
  ],
  "source_grounding": [
    {{
      "claim": "Assessment or observation claim",
      "source_chunk_id": "chunk_1",
      "source_title": "Source Section",
      "source_snippet": "Supporting source excerpt",
      "confidence": 0.95
    }}
  ]
}}
"""

def build_public_communication_prompt(
    model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    model_json = json.dumps(model.model_dump(exclude={"source_chunks"}), indent=2)
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are generating a PUBLIC COMMUNICATION / PRESS RELEASE / PUBLIC POST from the structured source analysis below.

TRANSFORMATION CONTROLS:
- Target Audience: {config.target_audience} (Accessible to citizens, media, or general public)
- Tone: {config.tone} (Clear, accessible, engaging, transparent, zero unnecessary jargon)
- Level of Detail: {config.level_of_detail}
- Communication Objective: {config.objective}
- Language: {config.language}

STRUCTURED INTERMEDIATE REPRESENTATION:
{model_json}

INSTRUCTIONS:
1. Transform the technical or policy source into an engaging, platform-neutral public announcement.
2. Demystify complex terms with clear analogies or plain explanations without distorting the underlying facts.
3. Include: Title/Headline, Opening Hook, Main Core Message, Key Supporting Facts (in plain language), Plain Language Explanation of significance, and Clear Closing Statement / Call to Action.
4. Preserve factual fidelity with source grounding citations.

Return ONLY a JSON object matching this schema:
{{
  "title": "Engaging, clear public headline",
  "opening_hook": "Compelling first paragraph that captures attention and explains why this matters",
  "main_message": "Core takeaway in accessible language",
  "supporting_facts": [
    "Key fact explained simply",
    "Key number or achievement put in relatable context"
  ],
  "plain_language_explanation": "Breakdown of what happened or what this means for everyday stakeholders",
  "closing_statement": "Concluding reassurance, guidance, or next step for the public",
  "source_grounding": [
    {{
      "claim": "Public statement claim",
      "source_chunk_id": "chunk_1",
      "source_title": "Source Section",
      "source_snippet": "Underlying fact from source",
      "confidence": 0.95
    }}
  ]
}}
"""

def build_presentation_prompt(
    model: StructuredContentModel,
    config: TransformationConfig
) -> str:
    model_json = json.dumps(model.model_dump(exclude={"source_chunks"}), indent=2)
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are generating a PRESENTATION OUTLINE (Slide-by-Slide Structure) from the structured source analysis below.

TRANSFORMATION CONTROLS:
- Target Audience: {config.target_audience}
- Tone: {config.tone}
- Level of Detail: {config.level_of_detail}
- Communication Objective: {config.objective}
- Language: {config.language}

STRUCTURED INTERMEDIATE REPRESENTATION:
{model_json}

INSTRUCTIONS:
1. Generate an end-to-end presentation deck outline (typically 4 to 6 slides depending on detail level).
2. Slide sequence should follow a logical narrative:
   - Slide 1: Title & Executive Context
   - Slide 2: Problem Statement & Key Observations
   - Slide 3: Evidence, Metrics & Analytical Findings
   - Slide 4: Strategic Risks & Operational Implications
   - Slide 5: Recommended Action Plan & Next Steps
3. For each slide provide: Slide Number, Slide Title, Key Bullet Points (concise, high impact), Supporting Data/Fact Callout, and detailed Speaker Notes (script for the presenter).
4. Provide source grounding citations for each slide's key claims.

Return ONLY a JSON object matching this schema:
{{
  "presentation_title": "Overarching Presentation Title",
  "target_audience": "{config.target_audience}",
  "estimated_duration_minutes": 15,
  "slides": [
    {{
      "slide_number": 1,
      "title": "Slide Title",
      "key_points": [
        "Concise bullet point 1",
        "Concise bullet point 2",
        "Concise bullet point 3"
      ],
      "supporting_information": "Key statistic, metric, or callout for this slide",
      "speaker_notes": "What the presenter should say out loud during this slide...",
      "source_grounding": [
        {{
          "claim": "Key slide claim",
          "source_chunk_id": "chunk_1",
          "source_title": "Section Title",
          "source_snippet": "Source quote",
          "confidence": 0.95
        }}
      ]
    }}
  ],
  "source_grounding": [
    {{
      "claim": "Overall presentation theme",
      "source_chunk_id": "chunk_1",
      "source_title": "Section Title",
      "source_snippet": "Source quote",
      "confidence": 0.95
    }}
  ]
}}
"""

def build_correction_prompt(
    output_type: str,
    failed_content: str,
    issues: List[str],
    model: StructuredContentModel
) -> str:
    model_json = json.dumps(model.model_dump(exclude={"source_chunks"}), indent=2)
    issues_list = "\n- ".join(issues)
    
    return f"""{SYSTEM_BASE_INSTRUCTION}

You are the VALIDATION CORRECTION ENGINE.
The previous generation for output type '{output_type}' failed validation with the following issues:
- {issues_list}

STRUCTURED INTERMEDIATE MODEL:
{model_json}

PREVIOUS FAILED OUTPUT:
{failed_content}

Fix all the identified issues and produce a strictly valid, complete, well-grounded JSON output adhering to the required schema for '{output_type}'. Output pure JSON only.
"""
