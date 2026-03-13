import logging

from trailtraining.util.logging_config import configure_logging


def reset_root_logger() -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    root.setLevel(logging.NOTSET)


def test_invalid_log_level_falls_back_to_info() -> None:
    reset_root_logger()
    configure_logging("not-a-real-level")
    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_valid_log_level_is_applied() -> None:
    reset_root_logger()
    configure_logging("DEBUG")
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
