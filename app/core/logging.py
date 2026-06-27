"""
Structured logging configuration.

Provides structured logging with context and correlation IDs for tracing.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with structured information.

        Args:
            record: Log record

        Returns:
            Formatted log string
        """
        # Base log data
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add request context if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "api_key"):
            # Mask API key for security
            api_key = record.api_key
            log_data["api_key"] = f"{api_key[:7]}...{api_key[-4:]}" if api_key else None

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # Format as key=value pairs
        formatted_parts = []
        for key, value in log_data.items():
            if isinstance(value, str) and " " in value:
                formatted_parts.append(f'{key}="{value}"')
            else:
                formatted_parts.append(f"{key}={value}")

        return " ".join(formatted_parts)


def setup_logging():
    """Configure application logging.

    Emits to stdout by default (collected by the ECS awslogs driver -> CloudWatch).
    When ``LOG_TO_FILE=True`` a rotating local file handler is added (and stdout can
    be disabled via ``LOG_TO_STDOUT=False``) so deployments can avoid CloudWatch.
    """
    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper())

    # Set formatter
    formatter = StructuredFormatter(
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    handlers: list[logging.Handler] = []

    # stdout handler (default; primary path for CloudWatch via container logs)
    if settings.log_to_stdout or not settings.log_to_file:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    # Local rotating file handler (avoids depending on CloudWatch)
    file_logging_error: str | None = None
    if settings.log_to_file:
        try:
            log_dir = os.path.dirname(os.path.abspath(settings.log_file_path))
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                settings.log_file_path,
                maxBytes=settings.log_file_max_bytes,
                backupCount=settings.log_file_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as exc:  # pragma: no cover - fall back to stdout
            file_logging_error = str(exc)
            if not handlers:
                stream_handler = logging.StreamHandler(sys.stdout)
                stream_handler.setLevel(log_level)
                stream_handler.setFormatter(formatter)
                handlers.append(stream_handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured: level={settings.log_level}, environment={settings.environment}, "
        f"to_file={settings.log_to_file}, to_stdout={settings.log_to_stdout}"
    )
    if file_logging_error:
        logger.error(
            f"Failed to initialize file logging at {settings.log_file_path}: {file_logging_error}"
        )


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for adding context to log messages."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message and add context.

        Args:
            msg: Log message
            kwargs: Keyword arguments

        Returns:
            Tuple of (message, kwargs)
        """
        # Add extra context from adapter
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)

        return msg, kwargs


def get_logger_with_context(name: str, **context) -> LoggerAdapter:
    """
    Get logger with context.

    Args:
        name: Logger name
        **context: Context to add to all log messages

    Returns:
        LoggerAdapter instance
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
