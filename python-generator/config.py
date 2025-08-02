import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Config:

    def __init__(self):
        self._validate_environment()

    def _validate_environment(self):
        required_vars = ["GEMINI_API_KEY"]
        missing_vars = []

        for var in required_vars:
            value = os.getenv(var)
            if not value or value.strip() == "" or value == "your_gemini_api_key_here":
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please set them in your .env file or environment."
            )

        logger.info("Environment variables validation successful")

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY")

    @property
    def output_dir(self) -> Path:
        return Path(os.getenv("OUTPUT_DIR", "/app/output"))

    @property
    def text_model_name(self) -> str:
        return os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")

    @property
    def image_model_name(self) -> str:
        return os.getenv(
            "GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation"
        )

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def server_host(self) -> str:
        return os.getenv("SERVER_HOST", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return int(os.getenv("SERVER_PORT", "8000"))


config = Config()
