#!/usr/bin/env python3
"""Adds one release entry to the top of docs/release/CHANGELOG.md (standard library only).

Run by the Release workflow with RELEASE_VERSION (x.y.z) and RELEASE_LOG (the commit lines).
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HEADER = (
    "# Changelog\n\n"
    "Written by the Release workflow from the commit log. Do not edit by hand.\n"
)

version = os.environ.get("RELEASE_VERSION", "").strip()
log = os.environ.get("RELEASE_LOG", "").strip()
if not version or not log:
    sys.exit("RELEASE_VERSION and RELEASE_LOG must be set")

path = Path(os.environ.get("CHANGELOG", "docs/release/CHANGELOG.md"))
text = path.read_text() if path.exists() else HEADER
if not text.startswith("# Changelog"):
    text = HEADER + "\n" + text

head, _, rest = text.partition("\n## ")
entry = f"## v{version} ({datetime.now(timezone.utc):%Y-%m-%d})\n\n{log}\n"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(head.rstrip("\n") + "\n\n" + entry + ("\n## " + rest if rest else ""))
print(f"added v{version} to {path}")
