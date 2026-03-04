from __future__ import annotations

import json
import re


def parse_features_text(raw_text: str) -> str:
    """Convert free-form feature text into normalized JSON string.

    Accepts plain lines, comma-separated text, and common bullet markers.
    """
    if not raw_text or not raw_text.strip():
        return "{}"

    normalized = raw_text.replace("\r\n", "\n")
    parts = re.split(r"\n|,", normalized)
    features: list[str] = []

    for part in parts:
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", part).strip()
        if cleaned:
            features.append(cleaned)

    if not features:
        return "{}"

    return json.dumps({"features": features}, ensure_ascii=False)

