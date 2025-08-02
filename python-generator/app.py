import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from google import genai
from google.genai import types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from config import config
from utils import (
    create_marketing_prompt,
    create_image_prompt,
    create_enhanced_placeholder,
    process_image_response,
)
from exponential_backoff import with_exponential_backoff, RetryOptions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Solara AI Generator",
    description="Advanced AI content generation using Google Gemini 2.0 Flash",
    version="1.0.0",
)


class GenerationRequest(BaseModel):
    campaignId: str = Field(..., description="Unique campaign identifier")
    prompt: str = Field(
        ..., min_length=1, max_length=2000, description="Content generation prompt"
    )


class GenerationResponse(BaseModel):
    campaignId: str
    generatedText: str
    imagePath: str


class GeneratorService:

    def __init__(self):
        self._initialize_api()
        self._setup_output_directory()
        self._initialize_models()

    def _initialize_api(self):
        try:
            self.client = genai.Client(api_key=config.gemini_api_key)
            logger.info("Gemini API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API client: {e}")
            raise

    def _setup_output_directory(self):
        self.output_dir = config.output_dir
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"Output directory configured: {self.output_dir}")

    def _initialize_models(self):
        self.text_model_name = config.text_model_name

        self.image_model_name = config.image_model_name

        try:
            self._validate_models()
            logger.info("Gemini models validated successfully")
        except Exception as e:
            logger.warning(f"Model validation failed: {e}")

    def _validate_models(self):
        try:
            test_response = self.client.models.generate_content(
                model=self.text_model_name,
                contents="Hello",
                config=types.GenerateContentConfig(
                    max_output_tokens=10, temperature=0.1
                ),
            )
            logger.info("Text model validation successful")

            test_image_response = self.client.models.generate_content(
                model=self.image_model_name,
                contents="Generate a small red circle",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    max_output_tokens=50,
                    temperature=0.1,
                ),
            )
            logger.info("Image model validation successful")

        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            raise

    async def generate_text(self, prompt: str, campaign_id: str) -> str:
        """
        Generate high-quality text content using Gemini 2.0 Flash.

        Implements best practices:
        - Structured prompting for marketing content
        - Proper error handling and retries
        - Token management
        - Response validation
        """
        logger.info(
            f"[{campaign_id}] Starting text generation for prompt: {prompt[:50]}..."
        )

        enhanced_prompt = create_marketing_prompt(prompt)

        def should_retry_api(error: Exception, _: int) -> bool:
            error_str = str(error).lower()
            if 'quota' in error_str or 'authentication' in error_str:
                return False
            return True

        try:
            response = await with_exponential_backoff(
                lambda: asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.text_model_name,
                    contents=enhanced_prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=1500,
                        temperature=0.7,
                        top_p=0.9,
                        top_k=40,
                        stop_sequences=["\n\n---", "\n\nEND"],
                    ),
                ),
                RetryOptions(
                    max_retries=3,
                    initial_delay_ms=2000,
                    max_delay_ms=30000,
                    should_retry=should_retry_api
                ),
                f"Gemini text generation for {campaign_id}"
            )

            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Empty response from Gemini text model")

            generated_text = response.candidates[0].content.parts[0].text

            if not generated_text or len(generated_text.strip()) < 10:
                raise ValueError("Generated text is too short or empty")

            logger.info(
                f"[{campaign_id}] Text generation completed successfully ({len(generated_text)} chars)"
            )
            return generated_text.strip()

        except Exception as e:
            logger.error(f"[{campaign_id}] Text generation failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Text generation failed: {str(e)}"
            )

    async def generate_image(self, prompt: str, campaign_id: str) -> str:
        logger.info(
            f"[{campaign_id}] Starting image generation for prompt: {prompt[:50]}..."
        )

        image_prompt = create_image_prompt(prompt)

        def should_retry_api(error: Exception, _: int) -> bool:
            error_str = str(error).lower()
            if 'quota' in error_str or 'authentication' in error_str:
                return False
            return True

        try:
            response = await with_exponential_backoff(
                lambda: asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.image_model_name,
                    contents=image_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=[
                            "TEXT",
                            "IMAGE",
                        ],
                        max_output_tokens=200,
                        temperature=0.8,
                        top_p=0.95,
                    ),
                ),
                RetryOptions(
                    max_retries=3,
                    initial_delay_ms=2000,
                    max_delay_ms=30000,
                    should_retry=should_retry_api
                ),
                f"Gemini image generation for {campaign_id}"
            )

            image_path = await self._process_image_response(
                response, campaign_id, prompt
            )

            if image_path:
                logger.info(
                    f"[{campaign_id}] Image generation completed successfully: {image_path}"
                )
                return image_path
            else:
                logger.warning(
                    f"[{campaign_id}] No image generated, creating placeholder"
                )
                return create_enhanced_placeholder(campaign_id, self.output_dir, prompt)

        except Exception as e:
            logger.error(f"[{campaign_id}] Image generation failed: {e}")
            logger.info(f"[{campaign_id}] Falling back to enhanced placeholder")
            return create_enhanced_placeholder(campaign_id, self.output_dir, prompt)

    async def _process_image_response(
        self, response, campaign_id: str, prompt: str
    ) -> Optional[str]:
        return process_image_response(response, campaign_id, self.output_dir, prompt)

    def get_health_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "models": {
                "text_model": self.text_model_name,
                "image_model": self.image_model_name,
            },
            "api": {
                "client_initialized": hasattr(self, "client"),
                "api_key_configured": bool(config.gemini_api_key),
            },
            "storage": {
                "output_directory": str(self.output_dir),
                "directory_writable": self.output_dir.is_dir()
                and os.access(self.output_dir, os.W_OK),
            },
        }


try:
    generator_service = GeneratorService()
    logger.info("Generator service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize generator service: {e}")
    raise


@app.post("/generate", response_model=GenerationResponse)
async def generate_content(request: GenerationRequest):
    campaign_id = request.campaignId
    prompt = request.prompt

    logger.info(f"[{campaign_id}] Starting content generation workflow")
    logger.info(f"[{campaign_id}] Prompt: {prompt}")

    try:
        text_task = generator_service.generate_text(prompt, campaign_id)
        image_task = generator_service.generate_image(prompt, campaign_id)

        generated_text, image_path = await asyncio.gather(text_task, image_task)

        logger.info(
            f"[{campaign_id}] Content generation workflow completed successfully"
        )

        return GenerationResponse(
            campaignId=campaign_id, generatedText=generated_text, imagePath=image_path
        )

    except Exception as e:
        logger.error(f"[{campaign_id}] Content generation workflow failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Content generation failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    try:
        health_status = generator_service.get_health_status()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


@app.get("/")
async def root():
    return {
        "service": "Solara AI Generator",
        "version": "1.0.0",
        "description": "Advanced AI content generation using Google Gemini 2.0 Flash",
        "endpoints": {"generate": "/generate", "health": "/health"},
    }


if __name__ == "__main__":
    logger.info("Starting Solara AI Generator Service...")
    logger.info(
        f"Using Gemini models - Text: gemini-2.0-flash, Image: gemini-2.0-flash-preview-image-generation"
    )

    uvicorn.run(
        app,
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level.lower(),
        access_log=True,
    )
