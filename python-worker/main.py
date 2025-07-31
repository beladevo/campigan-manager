import asyncio
import logging

import aio_pika
from aio_pika import connect

from config import config
from consumer import process_campaign_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger(__name__)


class CampaignWorker:
    """Lightweight RabbitMQ consumer that delegates content generation to python-generator service."""

    def __init__(self):
        self.rabbitmq_url = config.rabbitmq_url
        logger.info("Campaign worker initialized")

    async def connect_rabbitmq(self, max_retries=30, retry_delay=2):
        """Connect to RabbitMQ and set up queues with retry logic."""
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Connecting to RabbitMQ at {self.rabbitmq_url} (attempt {attempt + 1}/{max_retries})"
                )
                self.connection = await connect(self.rabbitmq_url)
                self.channel = await self.connection.channel()

                # Create queues that match NestJS microservices patterns
                self.generate_queue = await self.channel.declare_queue(
                    "campaign.generate", durable=True
                )
                self.result_queue = await self.channel.declare_queue(
                    "campaign.result", durable=True
                )

                logger.info("Successfully connected to RabbitMQ and set up queues")
                return

            except Exception as e:
                logger.warning(
                    f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    logger.error("Max retries reached. Unable to connect to RabbitMQ")
                    raise

                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

    async def start_consuming(self):
        """Start consuming messages from the generate queue."""
        try:
            logger.info(f"Setting up consumer for queue: {self.generate_queue.name}")

            # Create a message processor with queue references
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
        """Reconnect to RabbitMQ and restart consuming."""
        try:
            if hasattr(self, "connection"):
                await self.connection.close()
        except:
            pass

        await self.connect_rabbitmq()
        await self.start_consuming()

    async def is_connection_healthy(self):
        """Check if RabbitMQ connection is healthy."""
        try:
            if not hasattr(self, "connection") or self.connection.is_closed:
                return False
            # Try to declare a temporary queue to test connection
            temp_queue = await self.channel.declare_queue(
                "", exclusive=True, auto_delete=True
            )
            await temp_queue.delete()
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            return False


async def main():
    """Main worker function."""
    worker = CampaignWorker()

    try:
        # Connect to RabbitMQ with retries
        await worker.connect_rabbitmq()

        # Start consuming messages
        await worker.start_consuming()

        logger.info("Campaign worker is running. Press Ctrl+C to stop.")

        # Keep the worker running with periodic health checks
        try:
            while True:
                await asyncio.sleep(
                    config.health_check_interval
                )  # Health check interval
                if not await worker.is_connection_healthy():
                    logger.warning("Connection unhealthy, attempting to reconnect...")
                    await worker.reconnect_and_consume()

        except KeyboardInterrupt:
            logger.info("Shutting down campaign worker...")

    except Exception as e:
        logger.error(f"Worker failed: {e}")
        # Exit with non-zero code so Docker can restart if needed
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
