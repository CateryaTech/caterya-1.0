"""Tiny i18n layer (stdlib): locales/<lang>.json with English fallback. Evidence itself is always English/ASCII-stable."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Dict


@lru_cache(maxsize=8)
def _load(lang: str) -> Dict[str, str]:
    try:
        return json.loads(resources.files("caterya.locales").joinpath(f"{lang}.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def t(key: str, lang: str = "en") -> str:
    return _load(lang).get(key) or _load("en").get(key) or key
