import json
import logging
from typing import Tuple, Dict, Any
import httpx

from config import config

logger = logging.getLogger(__name__)


def parse_campaign_message(raw_body: str) -> Tuple[str, str]:
    """Parse campaign message from various formats."""
    data = json.loads(raw_body)
    logger.info(f"Parsed message data: {data}")

    if isinstance(data, dict):
        # Direct format: {"campaignId": "...", "prompt": "..."}
        if "campaignId" in data and "prompt" in data:
            campaign_id = data["campaignId"]
            prompt = data["prompt"]
        # NestJS microservices format: {"pattern": "campaign.generate", "data": {"campaignId": "...", "prompt": "..."}}
        elif "data" in data and isinstance(data["data"], dict):
            campaign_data = data["data"]
            campaign_id = campaign_data["campaignId"]
            prompt = campaign_data["prompt"]
        # Array format: [{"campaignId": "...", "prompt": "..."}]
        elif "0" in data or (isinstance(data, list) and len(data) > 0):
            campaign_data = data[0] if isinstance(data, list) else data["0"]
            campaign_id = campaign_data["campaignId"]
            prompt = campaign_data["prompt"]
        else:
            raise ValueError(f"Unrecognized message format: {data}")
    else:
        raise ValueError(f"Expected dict, got: {type(data)}")

    return campaign_id, prompt


async def make_http_request(
    method: str, url: str, data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Make HTTP request to python-generator service."""
    full_url = f"{config.generator_url}{url}"

    async with httpx.AsyncClient(
        timeout=config.rabbitmq_connection_timeout
    ) as client:
        if method.upper() == "POST":
            response = await client.post(full_url, json=data)
        elif method.upper() == "GET":
            response = await client.get(full_url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()
