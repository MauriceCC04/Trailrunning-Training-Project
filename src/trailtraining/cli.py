from __future__ import annotations

import os

from trailtraining.commands.common import apply_profile
from trailtraining.commands.parser import build_parser
from trailtraining.util.logging_config import configure_logging

__all__ = ["main"]


def main(argv: list[str] | None = None) -> None:
    configure_logging(os.getenv("TRAILTRAINING_LOG_LEVEL", "INFO"))
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_profile(args.profile)
    configure_logging(args.log_level)

    args.func(args)


if __name__ == "__main__":
    main()
