from typing import List, Set, Tuple, Dict, Any
from app.models.content_model import StructuredContentModel
from app.models.outputs import (
    ExecutiveSummary,
    AdvisoryBrief,
    PublicCommunication,
    PresentationOutline
)

class GroundingValidationError(ValueError):
    """Raised when an extracted structured model or transformed output references invalid or nonexistent source chunk IDs."""
    pass

class GroundingValidator:
    """Deterministically verifies that all source chunk references in models and transformations are valid."""

    @staticmethod
    def validate_model_grounding(model: StructuredContentModel) -> Tuple[bool, List[str]]:
        """Verifies that all chunk IDs cited in facts, entities, dates, metrics, risks, and recommendations
        actually exist in the model's source_chunks.
        
        Returns:
            (is_valid, error_messages)
        """
        valid_chunk_ids: Set[str] = {c.chunk_id for c in model.source_chunks}
        if not valid_chunk_ids:
            return False, ["Model contains zero source chunks. Grounding verification impossible."]

        errors: List[str] = []

        # 1. Key Facts
        for fact in model.key_facts:
            for cid in fact.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Key fact '{fact.fact_id}' references nonexistent chunk ID '{cid}'.")

        # 2. Entities
        for entity in model.entities:
            for cid in entity.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Entity '{entity.name}' references nonexistent chunk ID '{cid}'.")

        # 3. Dates
        for date_item in model.dates:
            for cid in date_item.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Date entry '{date_item.event}' references nonexistent chunk ID '{cid}'.")

        # 4. Metrics
        for metric in model.metrics:
            for cid in metric.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Metric '{metric.metric}' references nonexistent chunk ID '{cid}'.")

        # 5. Risks
        for risk in model.risks:
            for cid in risk.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Risk '{risk.risk[:40]}...' references nonexistent chunk ID '{cid}'.")

        # 6. Recommendations
        for rec in model.recommendations:
            for cid in rec.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Recommendation '{rec.action[:40]}...' references nonexistent chunk ID '{cid}'.")

        # 7. Important Statements
        for stmt in model.important_statements:
            for cid in stmt.source_chunk_ids:
                if cid not in valid_chunk_ids:
                    errors.append(f"Statement '{stmt.statement[:40]}...' references nonexistent chunk ID '{cid}'.")

        return len(errors) == 0, errors

    @classmethod
    def assert_grounding(cls, model: StructuredContentModel) -> None:
        """Asserts that the model is fully grounded. Raises GroundingValidationError if invalid."""
        is_valid, errors = cls.validate_model_grounding(model)
        if not is_valid:
            error_summary = "; ".join(errors[:5])
            if len(errors) > 5:
                error_summary += f" (...and {len(errors) - 5} more grounding errors)"
            raise GroundingValidationError(
                f"Source grounding validation failed: {error_summary}. Available chunks: {[c.chunk_id for c in model.source_chunks]}"
            )

    @staticmethod
    def validate_executive_summary_grounding(summary: ExecutiveSummary, valid_chunk_ids: Set[str]) -> Tuple[bool, List[str]]:
        """Verifies that all source_references in ExecutiveSummary cite valid source_chunk_ids."""
        errors: List[str] = []
        for ref in summary.source_references:
            if ref.source_chunk_id not in valid_chunk_ids:
                errors.append(f"Executive summary source reference '{ref.claim[:40]}...' cites nonexistent chunk ID '{ref.source_chunk_id}'.")
        return len(errors) == 0, errors

    @classmethod
    def assert_executive_summary_grounding(cls, summary: ExecutiveSummary, valid_chunk_ids: Set[str]) -> None:
        """Asserts that the executive summary is fully grounded. Raises GroundingValidationError if invalid."""
        is_valid, errors = cls.validate_executive_summary_grounding(summary, valid_chunk_ids)
        if not is_valid:
            error_summary = "; ".join(errors[:5])
            raise GroundingValidationError(
                f"Executive summary grounding validation failed: {error_summary}. Valid chunks: {sorted(list(valid_chunk_ids))}"
            )

    @staticmethod
    def validate_advisory_brief_grounding(advisory: AdvisoryBrief, valid_chunk_ids: Set[str]) -> Tuple[bool, List[str]]:
        """Verifies that all source_references in AdvisoryBrief cite valid source_chunk_ids."""
        errors: List[str] = []
        for ref in advisory.source_references:
            if ref.source_chunk_id not in valid_chunk_ids:
                errors.append(f"Advisory brief source reference '{ref.claim[:40]}...' cites nonexistent chunk ID '{ref.source_chunk_id}'.")
        return len(errors) == 0, errors

    @classmethod
    def assert_advisory_brief_grounding(cls, advisory: AdvisoryBrief, valid_chunk_ids: Set[str]) -> None:
        """Asserts that the advisory brief is fully grounded. Raises GroundingValidationError if invalid."""
        is_valid, errors = cls.validate_advisory_brief_grounding(advisory, valid_chunk_ids)
        if not is_valid:
            error_summary = "; ".join(errors[:5])
            raise GroundingValidationError(
                f"Advisory brief grounding validation failed: {error_summary}. Valid chunks: {sorted(list(valid_chunk_ids))}"
            )

    @staticmethod
    def validate_public_communication_grounding(comm: PublicCommunication, valid_chunk_ids: Set[str]) -> Tuple[bool, List[str]]:
        """Verifies that all source_references in PublicCommunication cite valid source_chunk_ids."""
        errors: List[str] = []
        for ref in comm.source_references:
            if ref.source_chunk_id not in valid_chunk_ids:
                errors.append(f"Public communication source reference '{ref.claim[:40]}...' cites nonexistent chunk ID '{ref.source_chunk_id}'.")
        return len(errors) == 0, errors

    @classmethod
    def assert_public_communication_grounding(cls, comm: PublicCommunication, valid_chunk_ids: Set[str]) -> None:
        """Asserts that the public communication is fully grounded. Raises GroundingValidationError if invalid."""
        is_valid, errors = cls.validate_public_communication_grounding(comm, valid_chunk_ids)
        if not is_valid:
            error_summary = "; ".join(errors[:5])
            raise GroundingValidationError(
                f"Public communication grounding validation failed: {error_summary}. Valid chunks: {sorted(list(valid_chunk_ids))}"
            )

    @staticmethod
    def validate_presentation_grounding(presentation: PresentationOutline, valid_chunk_ids: Set[str]) -> Tuple[bool, List[str]]:
        """Verifies that all source_references in PresentationOutline and slides cite valid source_chunk_ids."""
        errors: List[str] = []
        for ref in presentation.source_references:
            if ref.source_chunk_id not in valid_chunk_ids:
                errors.append(f"Presentation outline source reference '{ref.claim[:40]}...' cites nonexistent chunk ID '{ref.source_chunk_id}'.")
        for slide in presentation.slides:
            for ref in slide.source_references:
                if ref.source_chunk_id not in valid_chunk_ids:
                    errors.append(f"Slide {slide.slide_number} reference '{ref.claim[:40]}...' cites nonexistent chunk ID '{ref.source_chunk_id}'.")
        return len(errors) == 0, errors

    @classmethod
    def assert_presentation_grounding(cls, presentation: PresentationOutline, valid_chunk_ids: Set[str]) -> None:
        """Asserts that the presentation outline is fully grounded. Raises GroundingValidationError if invalid."""
        is_valid, errors = cls.validate_presentation_grounding(presentation, valid_chunk_ids)
        if not is_valid:
            error_summary = "; ".join(errors[:5])
            raise GroundingValidationError(
                f"Presentation outline grounding validation failed: {error_summary}. Valid chunks: {sorted(list(valid_chunk_ids))}"
            )
