import asyncio
import logging

import aio_pika
from aio_pika import connect

from config import config
from consumer import process_campaign_message
from exponential_backoff import with_exponential_backoff, RetryOptions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger(__name__)


class CampaignWorker:

    def __init__(self):
        self.rabbitmq_url = config.rabbitmq_url
        logger.info("Campaign worker initialized")

    async def connect_rabbitmq(self):
        async def _connect():
            logger.info(f"Connecting to RabbitMQ at {self.rabbitmq_url}")
            self.connection = await connect(self.rabbitmq_url)
            self.channel = await self.connection.channel()

            self.generate_queue = await self.channel.declare_queue(
                "campaign.generate", durable=True
            )
            self.result_queue = await self.channel.declare_queue(
                "campaign.result", durable=True
            )

            logger.info("Successfully connected to RabbitMQ and set up queues")

        def should_retry_connection(error: Exception, _: int) -> bool:
            return 'access-refused' not in str(error).lower()

        await with_exponential_backoff(
            _connect,
            RetryOptions(
                max_retries=10,
                initial_delay_ms=2000,
                max_delay_ms=30000,
                should_retry=should_retry_connection
            ),
            "RabbitMQ connection"
        )

    async def start_consuming(self):
        try:
            logger.info(f"Setting up consumer for queue: {self.generate_queue.name}")

            async def message_processor(message):
                await process_campaign_message(message, self.channel, self.result_queue)

            await self.generate_queue.consume(message_processor)
            logger.info(
                f"Started consuming campaign generation messages from queue: {self.generate_queue.name}"
            )

        except Exception as e:
            logger.error(f"Failed to start consuming: {e}")
            logger.info("Attempting to reconnect and restart consuming...")
            await self.reconnect_and_consume()

    async def reconnect_and_consume(self):
        try:
            if hasattr(self, "connection"):
                await self.connection.close()
        except:
            pass

        await self.connect_rabbitmq()
        await self.start_consuming()

    async def is_connection_healthy(self):
        try:
            if not hasattr(self, "connection") or self.connection.is_closed:
                return False
            temp_queue = await self.channel.declare_queue(
                "", exclusive=True, auto_delete=True
            )
            await temp_queue.delete()
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            return False


async def main():
    worker = CampaignWorker()

    try:
        await worker.connect_rabbitmq()

        await worker.start_consuming()

        logger.info("Campaign worker is running. Press Ctrl+C to stop.")

        try:
            while True:
                await asyncio.sleep(config.health_check_interval)
                if not await worker.is_connection_healthy():
                    logger.warning("Connection unhealthy, attempting to reconnect...")
                    await worker.reconnect_and_consume()

        except KeyboardInterrupt:
            logger.info("Shutting down campaign worker...")

    except Exception as e:
        logger.error(f"Worker failed: {e}")
        import sys

        sys.exit(1)
    finally:
        try:
            if hasattr(worker, "connection") and not worker.connection.is_closed:
                await worker.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


if __name__ == "__main__":
    asyncio.run(main())
