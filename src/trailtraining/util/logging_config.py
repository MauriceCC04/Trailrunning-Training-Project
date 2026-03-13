from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: str | int | None = None) -> None:
    raw_level = level if level is not None else "INFO"

    if isinstance(raw_level, int):
        numeric_level = raw_level
    else:
        normalized = str(raw_level).strip().upper()
        numeric_level = getattr(logging, normalized, logging.INFO)

    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(numeric_level)
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)
        return

    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT,
    )
