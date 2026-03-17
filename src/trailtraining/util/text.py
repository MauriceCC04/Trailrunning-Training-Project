from __future__ import annotations

import json
from typing import Any


def _safe_json_snippet(obj: Any, *, max_chars: int = 120_000) -> str:
    """Serialize *obj* to JSON, truncating at *max_chars* if needed.

    Never raises: falls back to str(obj) when json.dumps fails.
    Accepts max_chars as a keyword-only arg to match existing call-site signatures.
    """
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    if max_chars > 0 and len(s) > max_chars:
        return s[:max_chars] + "…"
    return s
