import json
import logging
from typing import Dict, Any
from datetime import datetime

import aio_pika
from aio_pika import Message

logger = logging.getLogger(__name__)


async def send_result(channel, result_queue, result_data: Dict[str, Any]):
    """Send result back via RabbitMQ to NestJS service."""
    try:
        campaign_id = result_data.get("campaignId", "unknown")
        
        logger.info(f"[{campaign_id}] Sending result back to NestJS service")
        logger.debug(f"[{campaign_id}] Result data: {result_data}")
        
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
        
    except Exception as e:
        campaign_id = result_data.get("campaignId", "unknown")
        logger.error(f"[{campaign_id}] Failed to send result: {e}")
        raise
