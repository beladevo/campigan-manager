import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Config:

    def __init__(self):
        self._validate_environment()

    def _validate_environment(self):
        required_vars = ["RABBITMQ_URL"]
        missing_vars = []

        for var in required_vars:
            value = os.getenv(var)
            if not value or value.strip() == "":
                missing_vars.append(var)

        generator_url = os.getenv("GENERATOR_URL")
        if not generator_url:
            logger.warning(
                "GENERATOR_URL not set, using default: http://python-generator:8000"
            )

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please set them in your .env file or environment."
            )

        logger.info("Environment variables validation successful")

    @property
    def rabbitmq_url(self) -> str:
        return os.getenv("RABBITMQ_URL")

    @property
    def generator_url(self) -> str:
        logger.info(
            "Using GENERATOR_URL: %s",
            os.getenv("GENERATOR_URL", "http://python-generator:8000"),
        )
        return os.getenv("GENERATOR_URL", "http://python-generator:8000")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def rabbitmq_connection_timeout(self) -> int:
        return int(os.getenv("RABBITMQ_TIMEOUT", "300"))

    @property
    def health_check_interval(self) -> int:
        return int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))


config = Config()
