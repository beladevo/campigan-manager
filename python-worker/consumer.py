import asyncio
import logging
import json
from typing import Dict, Any

import aio_pika
from aio_pika import Message
from datetime import datetime

from producer import send_result
from utils import make_http_request, parse_campaign_message

logger = logging.getLogger(__name__)


async def process_campaign_message(
    message: aio_pika.abc.AbstractIncomingMessage, channel, result_queue
):
    """Process incoming campaign generation message and delegate to python-generator."""
    async with message.process():
        try:
            raw_body = message.body.decode()
            logger.info(f"Received raw message: {raw_body}")

            campaign_id, prompt = parse_campaign_message(raw_body)

            logger.info(f"[{campaign_id}] Processing campaign generation request")
            logger.info(f"[{campaign_id}] Prompt: {prompt}")

            result = await delegate_to_generator(campaign_id, prompt)

            await send_result(channel, result_queue, result)

            logger.info(f"[{campaign_id}] Campaign processing completed successfully")

        except Exception as e:
            logger.error(f"Error processing campaign message: {e}")
            logger.error(f"Raw message body: {message.body.decode()}")

            try:
                raw_body = message.body.decode()
                campaign_id = extract_campaign_id_from_error(raw_body)

                error_result = {
                    "campaignId": campaign_id,
                    "generatedText": "",
                    "imagePath": "",
                    "error": str(e),
                }

                await send_result(channel, result_queue, error_result)
            except Exception as send_error:
                logger.error(f"Failed to send error result: {send_error}")


async def delegate_to_generator(campaign_id: str, prompt: str) -> Dict[str, Any]:
    """Delegate content generation to python-generator service via HTTP."""
    try:
        logger.info(f"[{campaign_id}] Delegating to python-generator service")

        generator_request = {"campaignId": campaign_id, "prompt": prompt}

        response = await make_http_request(
            method="POST", url="/generate", data=generator_request
        )

        logger.info(f"[{campaign_id}] Received response from python-generator")

        return {
            "campaignId": response["campaignId"],
            "generatedText": response["generatedText"],
            "imagePath": response["imagePath"],
            "error": None,
        }

    except Exception as e:
        logger.error(f"[{campaign_id}] Failed to delegate to python-generator: {e}")
        return {
            "campaignId": campaign_id,
            "generatedText": "",
            "imagePath": "",
            "error": f"Generation service error: {str(e)}",
        }


def extract_campaign_id_from_error(raw_body: str) -> str:
    """Extract campaign ID from raw message body for error reporting."""
    try:
        data = json.loads(raw_body)

        if isinstance(data, dict):
            if "campaignId" in data:
                return data["campaignId"]
            elif (
                "data" in data
                and isinstance(data["data"], dict)
                and "campaignId" in data["data"]
            ):
                return data["data"]["campaignId"]
            elif (
                "0" in data
                and isinstance(data["0"], dict)
                and "campaignId" in data["0"]
            ):
                return data["0"]["campaignId"]

    except Exception:
        pass

    return "unknown"
