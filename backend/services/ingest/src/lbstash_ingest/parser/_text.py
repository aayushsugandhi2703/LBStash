"""Regex flags and text prep for the parser: patterns compile with `FLAGS` (ASCII) and text goes through `js_spaces` first, so word and space classes match the web app."""

import re

# ASCII `\b \w \d` and case folding.
FLAGS = re.ASCII
FLAGS_I = re.ASCII | re.IGNORECASE

# Unicode whitespace -> a plain space; line terminators that `.` must not cross -> newline.
_TO_SPACE = '               　﻿'
_TO_NEWLINE = '\r  '
_TABLE = {ord(c): ' ' for c in _TO_SPACE} | {ord(c): '\n' for c in _TO_NEWLINE}


def js_spaces(text: str) -> str:
    """Rewrite exotic whitespace so ASCII `\\s` matches every Unicode space. One character in, one out."""
    return text.translate(_TABLE)


def rx(pattern: str, flags: int = FLAGS_I) -> re.Pattern[str]:
    return re.compile(pattern, flags)
