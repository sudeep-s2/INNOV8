import json
from typing import Dict, Any, List, Tuple
from app.models.schemas import (
    OutputType, ValidationResult, StructuredContentModel,
    ExecutiveSummaryOutput, AdvisoryBriefOutput, PublicCommOutput, PresentationOutput
)

class OutputValidator:
    """Validates generated outputs against structure, completeness, and source-grounding criteria."""

    @staticmethod
    def validate_output(
        output_type: OutputType,
        raw_output: Any,
        structured_model: StructuredContentModel
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        issues: List[str] = []
        
        # 1. Check if raw_output is a string or already a dict
        if isinstance(raw_output, str):
            clean_str = raw_output.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            elif clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            clean_str = clean_str.strip()
            
            try:
                data = json.loads(clean_str)
            except Exception as e:
                return False, [f"Invalid JSON syntax: {str(e)}"], {}
        elif isinstance(raw_output, dict):
            data = raw_output
        else:
            return False, ["Output is neither valid JSON string nor dictionary."], {}

        # 2. Output Type Specific Validations
        if output_type == "executive_summary":
            req_keys = ["title", "executive_overview", "key_findings", "important_facts_and_numbers", "risks_or_implications", "recommended_actions"]
            for k in req_keys:
                if k not in data or not data[k]:
                    issues.append(f"Missing or empty required field: '{k}'")
            
            if "key_findings" in data and len(data["key_findings"]) < 1:
                issues.append("Executive summary must have at least 1 key finding.")
            if "recommended_actions" in data and len(data["recommended_actions"]) < 1:
                issues.append("Executive summary must have at least 1 recommended action.")

        elif output_type == "advisory_brief":
            req_keys = ["title", "situation_context", "key_observations", "relevant_facts", "risk_and_impact_assessment", "recommended_actions", "important_caveats"]
            for k in req_keys:
                if k not in data or not data[k]:
                    issues.append(f"Missing or empty required field: '{k}'")
                    
            if "key_observations" in data and len(data["key_observations"]) < 1:
                issues.append("Advisory brief must contain at least 1 key observation.")
            if "recommended_actions" in data and len(data["recommended_actions"]) < 1:
                issues.append("Advisory brief must contain at least 1 recommended action.")

        elif output_type == "public_communication":
            req_keys = ["title", "opening_hook", "main_message", "supporting_facts", "plain_language_explanation", "closing_statement"]
            for k in req_keys:
                if k not in data or not data[k]:
                    issues.append(f"Missing or empty required field: '{k}'")

        elif output_type == "presentation_outline":
            req_keys = ["presentation_title", "slides"]
            for k in req_keys:
                if k not in data or not data[k]:
                    issues.append(f"Missing or empty required field: '{k}'")
            
            slides = data.get("slides", [])
            if not isinstance(slides, list) or len(slides) < 2:
                issues.append("Presentation outline must contain at least 2 slides.")
            else:
                for idx, slide in enumerate(slides, 1):
                    if not slide.get("title"):
                        issues.append(f"Slide {idx} is missing a title.")
                    if not slide.get("key_points") or len(slide.get("key_points", [])) == 0:
                        issues.append(f"Slide {idx} has no bullet points.")
                    if not slide.get("speaker_notes"):
                        issues.append(f"Slide {idx} is missing speaker notes.")

        # 3. Source Grounding Check
        grounding = data.get("source_grounding", [])
        if not isinstance(grounding, list):
            issues.append("Source grounding field must be a list of citation objects.")

        is_valid = len(issues) == 0
        return is_valid, issues, data

    @staticmethod
    def format_as_markdown(output_type: OutputType, data: Dict[str, Any]) -> str:
        """Converts structured JSON data to formatted markdown for user rendering, copy, and export."""
        lines: List[str] = []

        if output_type == "executive_summary":
            lines.append(f"# {data.get('title', 'Executive Summary')}\n")
            lines.append("## Executive Overview\n")
            lines.append(f"{data.get('executive_overview', '')}\n")
            
            lines.append("## Key Findings\n")
            for f in data.get("key_findings", []):
                lines.append(f"- {f}")
            lines.append("")

            lines.append("## Important Facts & Numbers\n")
            for n in data.get("important_facts_and_numbers", []):
                lines.append(f"- {n}")
            lines.append("")

            lines.append("## Risks & Implications\n")
            for r in data.get("risks_or_implications", []):
                lines.append(f"- {r}")
            lines.append("")

            lines.append("## Recommended Actions\n")
            for a in data.get("recommended_actions", []):
                lines.append(f"1. {a}")
            lines.append("")

        elif output_type == "advisory_brief":
            lines.append(f"# {data.get('title', 'ADVISORY BRIEF')}\n")
            lines.append("## Situation Context\n")
            lines.append(f"{data.get('situation_context', '')}\n")

            lines.append("## Key Observations\n")
            for o in data.get("key_observations", []):
                lines.append(f"- {o}")
            lines.append("")

            lines.append("## Relevant Facts & Telemetry\n")
            for rf in data.get("relevant_facts", []):
                lines.append(f"- {rf}")
            lines.append("")

            lines.append("## Risk & Impact Assessment\n")
            lines.append(f"{data.get('risk_and_impact_assessment', '')}\n")

            lines.append("## Recommended Actions\n")
            for idx, a in enumerate(data.get("recommended_actions", []), 1):
                lines.append(f"{idx}. {a}")
            lines.append("")

            lines.append("## Important Caveats & Assumptions\n")
            for c in data.get("important_caveats", []):
                lines.append(f"- {c}")
            lines.append("")

        elif output_type == "public_communication":
            lines.append(f"# {data.get('title', 'Public Announcement')}\n")
            lines.append(f"**{data.get('opening_hook', '')}**\n")
            lines.append("## Core Message\n")
            lines.append(f"{data.get('main_message', '')}\n")

            lines.append("## Key Facts for the Public\n")
            for f in data.get("supporting_facts", []):
                lines.append(f"- {f}")
            lines.append("")

            lines.append("## What This Means\n")
            lines.append(f"{data.get('plain_language_explanation', '')}\n")

            lines.append("## Next Steps & Public Guidance\n")
            lines.append(f"{data.get('closing_statement', '')}\n")

        elif output_type == "presentation_outline":
            lines.append(f"# {data.get('presentation_title', 'Presentation Deck Outline')}\n")
            lines.append(f"*Audience: {data.get('target_audience', 'General')} | Duration: ~{data.get('estimated_duration_minutes', 15)} mins*\n")
            
            slides = data.get("slides", [])
            for s in slides:
                lines.append(f"---")
                lines.append(f"### Slide {s.get('slide_number', '')}: {s.get('title', '')}\n")
                if s.get("supporting_information"):
                    lines.append(f"> **Key Highlight:** {s.get('supporting_information')}\n")
                lines.append("**Key Points:**")
                for p in s.get("key_points", []):
                    lines.append(f"- {p}")
                lines.append(f"\n🗣️ **Speaker Notes:**\n_{s.get('speaker_notes', '')}_\n")

        return "\n".join(lines)
