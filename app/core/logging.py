import logging
import sys
from typing import Any, Dict


def sanitize_message(msg: str) -> str:
    """Redacts potential API keys and sensitive tokens from log messages."""
    for secret_prefix in ["sk-", "Bearer "]:
        if secret_prefix in msg:
            parts = msg.split(secret_prefix)
            masked = []
            for i, part in enumerate(parts):
                if i == 0:
                    masked.append(part)
                else:
                    token_snippet = part[:4] + "..." if len(part) >= 4 else "..."
                    rest = part[20:] if len(part) > 20 else ""
                    masked.append(f"{secret_prefix}{token_snippet}{rest}")
            msg = "".join(masked)
    return msg


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.msg = sanitize_message(str(record.msg))
        return super().format(record)


def setup_logger(name: str = "eng_drawing") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger()
