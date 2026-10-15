from __future__ import annotations

import hashlib
import json
from typing import Any

_SHORT_LENGTH = 16


def short_hash(digest: str) -> str:
    """The first 16 hex characters of a digest: enough to name a working directory."""
    return digest[:_SHORT_LENGTH]


def work_key(data: str | bytes) -> str:
    """Name of a working directory derived from `data`: `short_hash` of its sha256."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return short_hash(hashlib.sha256(raw).hexdigest())


def compute_content_hash(*parts: Any) -> str:
    canonical = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
