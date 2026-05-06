"""
config/logger.py
Centralised logging for LobCut.
Call get_logger(__name__) in every module.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.settings import (
    LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOGS_DIR,
    NOISY_LOGGERS, SUPPRESS_HTTP_DEBUG_LOGS,
)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.DEBUG))

    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
    )
    fh.setFormatter(_FORMATTER)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(_FORMATTER)
    root.addHandler(sh)

    if SUPPRESS_HTTP_DEBUG_LOGS:
        for noisy_logger in NOISY_LOGGERS:
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
