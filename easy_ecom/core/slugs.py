from __future__ import annotations

import re
import unicodedata


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slugify_identifier(value: str, *, max_length: int, default: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM.sub("-", normalized.strip().lower())
    slug = _MULTI_DASH.sub("-", slug).strip("-")
    slug = slug[:max_length].rstrip("-")
    return slug or default


def with_suffix(base: str, index: int, *, max_length: int) -> str:
    if index <= 1:
        return base[:max_length].rstrip("-")
    suffix = f"-{index}"
    trimmed = base[: max_length - len(suffix)].rstrip("-")
    return f"{trimmed}{suffix}"
