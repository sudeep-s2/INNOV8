import io
from typing import List, Tuple
from pypdf import PdfReader
from pypdf.errors import PdfReadError

class PDFParserError(Exception):
    """Base exception for PDF parsing errors."""
    pass

class EncryptedPDFError(PDFParserError):
    """Raised when PDF is encrypted or password-protected."""
    pass

class EmptyPDFError(PDFParserError):
    """Raised when PDF contains no pages or zero extractable text."""
    pass

class MalformedPDFError(PDFParserError):
    """Raised when PDF binary is corrupted or unreadable."""
    pass

class PdfParser:
    """Extracts text page-by-page from PDF documents using pypdf."""

    @staticmethod
    def extract_pages(file_bytes: bytes) -> List[Tuple[int, str]]:
        """Extracts text from PDF bytes returning a list of (page_number, page_text).
        
        Raises:
            EmptyPDFError: If file is empty or has 0 extractable characters.
            EncryptedPDFError: If PDF is encrypted and requires a password.
            MalformedPDFError: If file is corrupted or not a valid PDF.
        """
        if not file_bytes:
            raise EmptyPDFError("Uploaded PDF file is empty (0 bytes).")

        try:
            stream = io.BytesIO(file_bytes)
            reader = PdfReader(stream)
        except (PdfReadError, Exception) as e:
            raise MalformedPDFError(f"Failed to read PDF document: {str(e)}") from e

        if reader.is_encrypted:
            try:
                # Try decrypting with empty password
                reader.decrypt("")
            except Exception as e:
                raise EncryptedPDFError("PDF document is encrypted and password-protected.") from e

        if len(reader.pages) == 0:
            raise EmptyPDFError("PDF document contains zero pages.")

        extracted_pages: List[Tuple[int, str]] = []
        total_text_len = 0

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            extracted_pages.append((page_num, text))
            total_text_len += len(text.strip())

        if total_text_len == 0:
            raise EmptyPDFError(
                "PDF contains no extractable text (it may be a scanned image-only PDF, which requires OCR)."
            )

        return extracted_pages
