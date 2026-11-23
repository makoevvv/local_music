from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def resolve_level(level: str) -> str:
    name = level.strip().upper()
    if name not in _LEVELS:
        return "INFO"
    return name


def build_log_config(level: str) -> dict[str, Any]:
    resolved = resolve_level(level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "app.core.logging.JsonFormatter"},
        },
        "handlers": {
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
                "level": resolved,
            },
        },
        "root": {"handlers": ["json"], "level": resolved},
        "loggers": {
            "uvicorn": {"handlers": ["json"], "level": resolved, "propagate": False},
            "uvicorn.error": {"handlers": ["json"], "level": resolved, "propagate": False},
            "uvicorn.access": {"handlers": ["json"], "level": resolved, "propagate": False},
        },
    }


def configure_logging(level: str) -> None:
    logging.config.dictConfig(build_log_config(level))
