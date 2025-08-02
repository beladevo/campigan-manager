import json
import logging
from typing import Dict, Any
from datetime import datetime

import aio_pika
from aio_pika import Message

from exponential_backoff import with_exponential_backoff, RetryOptions

logger = logging.getLogger(__name__)


async def send_result(channel, result_queue, result_data: Dict[str, Any]):
    campaign_id = result_data.get("campaignId", "unknown")
    
    logger.info(f"[{campaign_id}] Sending result back to NestJS service")
    logger.debug(f"[{campaign_id}] Result data: {result_data}")
    
    async def _send_message():
        nestjs_message = {
            "pattern": "campaign.result",
            "data": result_data
        }
        
        message = Message(
            json.dumps(nestjs_message).encode(),
            message_id=campaign_id,
            timestamp=datetime.now(),
            headers={'pattern': 'campaign.result'}
        )
        
        await channel.default_exchange.publish(
            message, routing_key=result_queue.name
        )
        
        logger.info(f"[{campaign_id}] Result sent successfully to queue: {result_queue.name}")

    def should_retry_publish(error: Exception, _: int) -> bool:
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in [
            'connection', 'timeout', 'temporary', 'unavailable'
        ])

    await with_exponential_backoff(
        _send_message,
        RetryOptions(
            max_retries=3,
            initial_delay_ms=1000,
            max_delay_ms=10000,
            should_retry=should_retry_publish
        ),
        f"Publishing result for campaign {campaign_id}"
    )
