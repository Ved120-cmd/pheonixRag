"""Structured logging setup: JSON console output + rotating file handler."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.config.settings import get_settings

settings = get_settings()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "phoenixrag.log"

_JSON_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    """Configure root logging once, at application startup."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Avoid duplicate handlers on reload/re-import.
    if root_logger.handlers:
        return

    formatter = jsonlogger.JsonFormatter(_JSON_FORMAT, rename_fields={"asctime": "timestamp"})

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler: caps individual log files at 10MB, keeps 5
    # backups (~50MB max on disk) so logs can't silently fill the volume.
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.app_debug else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
