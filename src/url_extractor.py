import re

URL_PATTERN = re.compile(
    r"(?<!@)\b(?:https?://|www\.)[^\s<>\"'`]+|"
    r"(?<!@)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}(?:[/?#][^\s<>\"'`]*)?",
    re.IGNORECASE,
)
TRAILING_PUNCTUATION = ".,;:!?)]}"


def extract_urls(text: str) -> list[str]:
    """Return URLs and domains found in untrusted text."""
    return [
        match.group().rstrip(TRAILING_PUNCTUATION)
        for match in URL_PATTERN.finditer(text)
    ]
