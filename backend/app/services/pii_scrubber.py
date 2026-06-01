"""
PII scrubber — applied to ANY text that leaves the backend toward the
LLM (or any external system). Replaces name/phone/email/SSN/DOB/address
with role tokens like [NAME], [PHONE]. The original PHI stays encrypted
in Postgres; only the scrubbed copy goes to Modal.
"""
import re


_PATTERNS = [
    # SSN-style 9-digit (most aggressive first)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # phone numbers (US + intl-ish)
    (re.compile(r"\b\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?"
                r"\d{3,4}[\s.-]?\d{3,4}\b"), "[PHONE]"),
    # email
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    # explicit "Name: ..." pattern (common in intake forms).
    # Requires either a following intake field (Age/Gender/...) OR end of string.
    (re.compile(r"(?i)\bName\s*:\s*[A-Z][\w\s.'-]{1,40}?"
                r"(?=\s+(?:Age|Gender|Occupation|Education|Marital)\b|\s*$)"),
     "Name: [NAME]"),
    # DOB
    (re.compile(r"\b(?:DOB|D\.O\.B\.?|Date\s+of\s+Birth)\s*:?\s*"
                r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b", re.I), "DOB: [DATE]"),
    # Street addresses (number + street name)
    (re.compile(r"\b\d{1,5}\s+[A-Z][\w\s.]{2,30}\s+"
                r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|"
                r"Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b"), "[ADDRESS]"),
]


def scrub(text: str) -> str:
    """Apply all PII patterns; return cleaned text."""
    if not text:
        return text
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def scrub_dict(d: dict, fields: list[str]) -> dict:
    """Convenience: scrub only the named string fields in d."""
    return {k: (scrub(v) if k in fields and isinstance(v, str) else v)
            for k, v in d.items()}
