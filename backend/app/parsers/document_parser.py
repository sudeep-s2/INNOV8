from typing import List, Tuple, Optional
from app.models.source import SourceChunk
from app.parsers.sanitizer import sanitize_text
from app.parsers.chunker import SemanticChunker
from app.parsers.text_parser import TextParser, EmptyTextError
from app.parsers.pdf_parser import PdfParser, EmptyPDFError, EncryptedPDFError, MalformedPDFError

class DocumentParser:
    """Coordinates text extraction, sanitization, and semantic chunking across supported document formats."""

    def __init__(self, max_chunk_size: int = 1200, min_chunk_size: int = 250):
        self.chunker = SemanticChunker(max_chunk_size=max_chunk_size, min_chunk_size=min_chunk_size)

    def parse_text(self, raw_text: str) -> Tuple[str, List[SourceChunk]]:
        """Ingests raw pasted text, sanitizes it, and produces semantic chunks."""
        validated_text = TextParser.validate_string(raw_text)
        sanitized = sanitize_text(validated_text)
        if not sanitized:
            raise EmptyTextError("Text content is empty after sanitization.")

        chunks, _ = self.chunker.chunk_text(
            sanitized_text=sanitized,
            page_number=None,
            source_location_prefix="Pasted Text",
            start_chunk_index=1,
            global_char_offset=0
        )
        return sanitized, chunks

    def parse_txt_file(self, file_bytes: bytes, filename: str = "document.txt") -> Tuple[str, List[SourceChunk]]:
        """Ingests TXT file bytes, decodes, sanitizes, and produces semantic chunks."""
        raw_text = TextParser.parse_bytes(file_bytes)
        sanitized = sanitize_text(raw_text)
        if not sanitized:
            raise EmptyTextError(f"TXT document '{filename}' contains no text after sanitization.")

        chunks, _ = self.chunker.chunk_text(
            sanitized_text=sanitized,
            page_number=None,
            source_location_prefix=filename,
            start_chunk_index=1,
            global_char_offset=0
        )
        return sanitized, chunks

    def parse_pdf_file(self, file_bytes: bytes, filename: str = "document.pdf") -> Tuple[str, List[SourceChunk]]:
        """Ingests PDF file bytes, extracts text page-by-page, sanitizes, and produces page-aware chunks."""
        pages = PdfParser.extract_pages(file_bytes)
        all_chunks: List[SourceChunk] = []
        chunk_idx = 1
        full_sanitized_pages: List[str] = []
        global_char_offset = 0

        for page_num, raw_page_text in pages:
            sanitized_page = sanitize_text(raw_page_text)
            if not sanitized_page:
                continue

            page_chunks, next_chunk_idx = self.chunker.chunk_text(
                sanitized_text=sanitized_page,
                page_number=page_num,
                source_location_prefix=f"{filename} (Page {page_num})",
                start_chunk_index=chunk_idx,
                global_char_offset=global_char_offset
            )

            all_chunks.extend(page_chunks)
            chunk_idx = next_chunk_idx
            full_sanitized_pages.append(sanitized_page)
            global_char_offset += len(sanitized_page) + 2

        if not all_chunks:
            raise EmptyPDFError(f"PDF document '{filename}' contains no extractable text.")

        full_sanitized = "\n\n".join(full_sanitized_pages)
        return full_sanitized, all_chunks
