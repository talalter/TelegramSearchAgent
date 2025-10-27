"""Configuration utilities for the Telegram monitor package."""


import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_LOG_FILE = Path("telegram_monitor.log")
_LOGGING_CONFIGURED = False


def _configure_root_logger(level: int = logging.INFO) -> None:
    """Configure the root logger with UTF-8 file and stream handlers."""
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    _LOGGING_CONFIGURED = True


def setup_environment() -> None:
    """Load environment variables and configure logging once per process."""
    load_dotenv()
    _configure_root_logger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger instance."""
    setup_environment()
    return logging.getLogger(name)


# Ensure configuration occurs on import for convenience.
setup_environment()