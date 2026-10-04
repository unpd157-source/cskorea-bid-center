#!/usr/bin/env python3
"""Validate a freshly collected data file before replacing production data."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate_data.py SOURCE DESTINATION", file=sys.stderr)
        return 2
    source, destination = map(Path, sys.argv[1:])
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data.get("meta"), dict) or not isinstance(data.get("notices"), list):
        raise ValueError("invalid bid data document")
    if data["meta"].get("source") != "KONEPS OpenAPI":
        raise ValueError("production collection must identify the KONEPS source")
    if data["meta"].get("count") != len(data["notices"]):
        raise ValueError("notice count does not match metadata")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
    print(f"Validated and installed {len(data['notices'])} notices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
