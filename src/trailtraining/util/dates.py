from __future__ import annotations

from datetime import date
from typing import Any, Optional


def _as_date(s: Any) -> Optional[date]:
    """Parse a date from an ISO-8601 string, returning None on any failure.

    Accepts Any so callers never need to pre-check for None values from dict.get().
    Slices to [:10] so datetime strings ("2026-03-14T…") work without extra handling.
    """
    if not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None
