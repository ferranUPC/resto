from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_content_hash(*parts: Any) -> str:
    canonical = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
