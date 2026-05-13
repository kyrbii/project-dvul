import logging
import logging.config
import os


def setup_logging():
    """Configure logging for the backend application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "backend.log")
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"

    # Ensure the log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": log_format,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": log_level,
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": log_level,
                    "filename": log_file,
                    "encoding": "utf-8",
                    "mode": "a",
                },
            },
            "loggers": {
                "backend": {
                    "handlers": ["console", "file"],
                    "level": log_level,
                    "propagate": False,
                }
            },
            "root": {
                "level": "WARNING",
                "handlers": ["console"],
            },
        }
    )


def get_backend_logger():
    """Get the configured backend logger."""
    return logging.getLogger("backend")