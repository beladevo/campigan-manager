import json
import logging
from typing import Tuple, Dict, Any
import httpx

from config import config
from exponential_backoff import with_exponential_backoff, RetryOptions

logger = logging.getLogger(__name__)


def parse_campaign_message(raw_body: str) -> Tuple[str, str]:
    data = json.loads(raw_body)
    logger.info(f"Parsed message data: {data}")

    if isinstance(data, dict):
        if "campaignId" in data and "prompt" in data:
            campaign_id = data["campaignId"]
            prompt = data["prompt"]
        elif "data" in data and isinstance(data["data"], dict):
            campaign_data = data["data"]
            campaign_id = campaign_data["campaignId"]
            prompt = campaign_data["prompt"]
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
    full_url = f"{config.generator_url}{url}"

    async def _make_request():
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

    def should_retry_http(error: Exception, _: int) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code >= 500 or error.response.status_code == 429
        
        return isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout))

    return await with_exponential_backoff(
        _make_request,
        RetryOptions(
            max_retries=3,
            initial_delay_ms=1000,
            max_delay_ms=10000,
            should_retry=should_retry_http
        ),
        f"HTTP {method} {full_url}"
    )
