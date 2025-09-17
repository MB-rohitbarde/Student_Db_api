"""Application logging configuration with rotating file handlers.

Creates console and file handlers, with a consistent formatter including
timestamp, level, logger name, and message. Also sets up a separate error
log file for warnings and above.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def init_logging(log_dir: str | None = None) -> None:
    """Initialize application-wide logging.

    - Writes info-level logs to logs/app.log (rotating)
    - Writes warnings and errors to logs/error.log (rotating)
    - Always logs to console as well
    """
    logs_path = Path(log_dir or "logs")
    logs_path.mkdir(parents=True, exist_ok=True)

    # Common formatter: 2025-09-15 12:34:56 | INFO | logger | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating app log (info and above)
    app_log_path = logs_path / "app.log"
    existing_app_handler = next(
        (h for h in root_logger.handlers if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '').endswith(str(app_log_path))),
        None,
    )
    if not existing_app_handler:
        app_file_handler = RotatingFileHandler(
            app_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        app_file_handler.setLevel(logging.INFO)
        app_file_handler.setFormatter(formatter)
        root_logger.addHandler(app_file_handler)

    # Rotating error log (warnings and above)
    err_log_path = logs_path / "error.log"
    existing_err_handler = next(
        (h for h in root_logger.handlers if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '').endswith(str(err_log_path))),
        None,
    )
    if not existing_err_handler:
        err_file_handler = RotatingFileHandler(
            err_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        err_file_handler.setLevel(logging.WARNING)
        err_file_handler.setFormatter(formatter)
        root_logger.addHandler(err_file_handler)

    logging.getLogger(__name__).info("Logging initialized.")


