import re
from typing import List, Optional, Tuple
from app.models.source import SourceChunk

# Common heading patterns in technical and intelligence reports
HEADING_REGEX = re.compile(
    r"^(?:(?:[0-9]+(?:\.[0-9]+)*\.?|[A-Z]\.)\s+[A-Z0-9\s\-_:]{3,60}|"
    r"(?:SECTION|CHAPTER|PART|APPENDIX|ANNEX)\s+[0-9A-ZIVX]+[:\s\-_].*|"
    r"#{1,6}\s+.+|"
    r"[A-Z0-9\s\-_]{3,40}:)$",
    re.IGNORECASE | re.MULTILINE
)

# Sentence boundary regex for fallback splitting
SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

class SemanticChunker:
    """Splits structured and unstructured text into addressable, semantic SourceChunk objects."""

    def __init__(self, max_chunk_size: int = 1200, min_chunk_size: int = 250):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits large text into sentence units."""
        sentences = SENTENCE_SPLIT_REGEX.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_text(
        self,
        sanitized_text: str,
        page_number: Optional[int] = None,
        source_location_prefix: Optional[str] = None,
        start_chunk_index: int = 1,
        global_char_offset: int = 0
    ) -> Tuple[List[SourceChunk], int]:
        """Segments sanitized text into semantic chunks.
        
        Returns:
            (chunks, next_chunk_index)
        """
        if not sanitized_text.strip():
            return [], start_chunk_index

        paragraphs = [p.strip() for p in sanitized_text.split("\n\n") if p.strip()]
        chunks: List[SourceChunk] = []
        chunk_idx = start_chunk_index

        current_paragraphs: List[str] = []
        current_len = 0
        current_heading: Optional[str] = None

        def flush_chunk():
            nonlocal chunk_idx, current_paragraphs, current_len
            if not current_paragraphs:
                return

            chunk_content = "\n\n".join(current_paragraphs).strip()
            if not chunk_content:
                current_paragraphs = []
                current_len = 0
                return

            # Compute offsets in sanitized_text
            # Find the position of chunk_content in sanitized_text
            char_start = sanitized_text.find(chunk_content)
            if char_start != -1:
                abs_start = global_char_offset + char_start
                abs_end = abs_start + len(chunk_content)
            else:
                abs_start = global_char_offset
                abs_end = global_char_offset + len(chunk_content)

            loc = current_heading or source_location_prefix
            if page_number and not loc:
                loc = f"Page {page_number}"
            elif page_number and loc and f"Page {page_number}" not in loc:
                loc = f"Page {page_number} - {loc}"

            chunks.append(
                SourceChunk(
                    chunk_id=f"chunk_{chunk_idx}",
                    text=chunk_content,
                    page_number=page_number,
                    source_location=loc,
                    char_start=abs_start,
                    char_end=abs_end
                )
            )
            chunk_idx += 1
            current_paragraphs = []
            current_len = 0

        for para in paragraphs:
            # Check if this paragraph is a section heading
            is_heading = bool(HEADING_REGEX.match(para.strip()))
            
            # If paragraph itself is longer than max_chunk_size, break it into sentence-level sub-chunks
            if len(para) > self.max_chunk_size:
                flush_chunk()
                sentences = self._split_into_sentences(para)
                sub_para_group: List[str] = []
                sub_len = 0

                for s in sentences:
                    if sub_len + len(s) > self.max_chunk_size and sub_para_group:
                        current_paragraphs = sub_para_group
                        flush_chunk()
                        sub_para_group = [s]
                        sub_len = len(s)
                    else:
                        sub_para_group.append(s)
                        sub_len += len(s) + 1

                if sub_para_group:
                    current_paragraphs = sub_para_group
                    flush_chunk()
                continue

            if is_heading:
                # Flush existing content before starting new section
                if current_paragraphs and current_len >= self.min_chunk_size:
                    flush_chunk()
                current_heading = para.strip()
                current_paragraphs.append(para)
                current_len += len(para)
                continue

            if current_len + len(para) > self.max_chunk_size and current_paragraphs:
                flush_chunk()

            current_paragraphs.append(para)
            current_len += len(para) + 2

        flush_chunk()
        return chunks, chunk_idx
