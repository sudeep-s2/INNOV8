import re
import unicodedata

def sanitize_text(raw_text: str) -> str:
    """Deterministically cleans and sanitizes raw text while preserving all semantic content.
    
    Operations:
    1. Removes UTF-8 BOM if present.
    2. Normalizes unicode characters (NFKC).
    3. Normalizes all line breaks (CRLF, CR -> LF).
    4. Cleans non-printable control characters while preserving tabs and newlines.
    5. Collapses excessive horizontal whitespace (tabs/spaces) within lines.
    6. Normalizes consecutive newlines (max 2 consecutive newlines) to preserve paragraph structure.
    7. Preserves all numbers, dates, punctuation, CVEs, IPs, ports, and technical strings intact.
    """
    if not raw_text:
        return ""

    # 1. Strip BOM
    text = raw_text.lstrip("\ufeff")

    # 2. Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # 3. Line break normalization
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 4. Remove unprintable control chars (preserve \n and \t)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))

    # 5. Clean horizontal whitespace (collapse spaces/tabs on each line)
    lines = text.split("\n")
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    # Reconstruct text
    text = "\n".join(cleaned_lines)

    # 6. Collapse 3+ newlines to exactly 2 newlines (preserve paragraph boundaries)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
