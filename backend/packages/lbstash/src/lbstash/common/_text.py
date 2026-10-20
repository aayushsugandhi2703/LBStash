"""Text helpers shared by tags and the password policy."""


def utf16_len(s: str) -> int:
    """Length in UTF-16 code units, as JavaScript's `.length` counts (matches the web app)."""
    return len(s.encode('utf-16-le')) // 2
