# src/trailtraining/util/logging_config.py
from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    """
    Central logging setup for the CLI.

    Priority:
      1) CLI arg (--log-level)
      2) env TRAILTRAINING_LOG_LEVEL
      3) default INFO
    """
    raw = (level or os.getenv("TRAILTRAINING_LOG_LEVEL") or "INFO").upper().strip()
    if raw not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raw = "INFO"

    logging.basicConfig(
        level=getattr(logging, raw),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,  # make CLI override predictable
    )