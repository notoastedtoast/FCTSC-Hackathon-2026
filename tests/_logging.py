"""Reduce expected error-log noise during negative-path tests."""

import logging


for logger_name in ("src.main", "src.analyzer", "src.database"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)
