#!/usr/bin/env python3
"""Create the static output directory used by Sites hosting."""

from pathlib import Path
import shutil

source = Path("public")
destination = Path("dist")
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
print(f"Copied {source} to {destination}")
