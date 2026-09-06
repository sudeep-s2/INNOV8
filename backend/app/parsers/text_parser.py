class TextParserError(Exception):
    """Base exception for text file parsing errors."""
    pass

class EmptyTextError(TextParserError):
    """Raised when text file or input is empty."""
    pass

class TextParser:
    """Decodes and validates text from raw strings or byte streams."""

    @staticmethod
    def parse_bytes(file_bytes: bytes) -> str:
        """Decodes uploaded file bytes with UTF-8 / UTF-8-SIG / Latin-1 fallback."""
        if not file_bytes:
            raise EmptyTextError("Uploaded text file is empty (0 bytes).")

        # Try standard encodings in order
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        decoded_text = None

        for enc in encodings:
            try:
                decoded_text = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if decoded_text is None:
            raise TextParserError("Unable to decode file content using supported text encodings.")

        if not decoded_text.strip():
            raise EmptyTextError("Text file contains only whitespace.")

        return decoded_text

    @staticmethod
    def validate_string(text: str) -> str:
        """Validates raw text input string."""
        if not text or not text.strip():
            raise EmptyTextError("Provided source text is empty.")
        return text
