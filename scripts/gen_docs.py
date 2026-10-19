#!/usr/bin/env python3
"""Regenerate docs/METRICS.md, docs/PARAMETERS.md, docs/REGULATORY.md and schemas/ (same as `caterya docs`)."""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from caterya.docgen import generate  # noqa: E402

generate(str(root))
print("generated docs and schemas under", root)
