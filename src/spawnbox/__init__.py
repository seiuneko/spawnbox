from __future__ import annotations

import logging
import sys

__version__ = "0.1.0"

LOG_FORMAT = "[spawnbox] %(message)s"


def setup_logging(verbosity: int = 0) -> None:
    """Configure logging level based on verbosity count."""
    level = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }.get(verbosity, logging.DEBUG)
    logging.basicConfig(level=level, format=LOG_FORMAT, stream=sys.stderr)
