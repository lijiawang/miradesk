from typing import Optional


def truncate(text: Optional[str], limit: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...({len(text)} chars)"

