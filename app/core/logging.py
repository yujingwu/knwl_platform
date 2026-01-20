import logging
from typing import Any


def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
    )


def log_request(data: dict[str, Any]) -> None:
    logger = logging.getLogger("app.request")
    logger.info(data)

