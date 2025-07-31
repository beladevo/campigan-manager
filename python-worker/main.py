import os
import asyncio
import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

import aio_pika
from aio_pika import connect, Message, ExchangeType
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

class CampaignWorker:
    def __init__(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://rabbitmq:rabbitmq@rabbitmq:5672")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "AIzaSyCFyqorPdLlXdE459IS2h1T7N8Ol2pXrV4")
        self.output_dir = Path("/app/output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.gemini_api_key)
        self.text_model_name = "gemini-2.0-flash"
        self.image_model_name = "gemini-2.0-flash-preview-image-generation"
        
        logger.info("Campaign worker initialized")

    async def connect_rabbitmq(self, max_retries=30, retry_delay=2):
        """Connect to RabbitMQ and set up queues with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to RabbitMQ at {self.rabbitmq_url} (attempt {attempt + 1}/{max_retries})")
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
                logger.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached. Unable to connect to RabbitMQ")
                    raise
                
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

    async def start_consuming(self):
        """Start consuming messages from the generate queue"""
        try:
            logger.info(f"Setting up consumer for queue: {self.generate_queue.name}")
            await self.generate_queue.consume(self.process_campaign_message)
            logger.info(f"Started consuming campaign generation messages from queue: {self.generate_queue.name}")
            
        except Exception as e:
            logger.error(f"Failed to start consuming: {e}")
            # Try to reconnect and restart consuming
            logger.info("Attempting to reconnect and restart consuming...")
            await self.reconnect_and_consume()

    async def reconnect_and_consume(self):
        """Reconnect to RabbitMQ and restart consuming"""
        try:
            if hasattr(self, 'connection'):
                await self.connection.close()
        except:
            pass
        
        await self.connect_rabbitmq()
        await self.start_consuming()

    async def is_connection_healthy(self):
        """Check if RabbitMQ connection is healthy"""
        try:
            if not hasattr(self, 'connection') or self.connection.is_closed:
                return False
            # Try to declare a temporary queue to test connection
            temp_queue = await self.channel.declare_queue("", exclusive=True, auto_delete=True)
            await temp_queue.delete()
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            return False

    async def process_campaign_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        """Process incoming campaign generation message"""
        async with message.process():
            try:
                # Log raw message for debugging
                raw_body = message.body.decode()
                logger.info(f"Received raw message: {raw_body}")
                
                # Parse message - handle different possible formats
                data = json.loads(raw_body)
                logger.info(f"Parsed message data: {data}")
                
                # Handle different message formats
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
                
                logger.info(f"[{campaign_id}] Processing campaign generation request")
                logger.info(f"[{campaign_id}] Prompt: {prompt}")
                
                # Generate content
                generated_text = await self.generate_text(prompt, campaign_id)
                image_path = await self.generate_image(prompt, campaign_id)
                
                # Send result back
                await self.send_result(campaign_id, generated_text, image_path)
                
                logger.info(f"[{campaign_id}] Campaign processing completed successfully")
                
            except Exception as e:
                logger.error(f"Error processing campaign message: {e}")
                logger.error(f"Raw message body: {message.body.decode()}")
                
                # Send error result
                try:
                    raw_body = message.body.decode()
                    data = json.loads(raw_body)
                    
                    # Try to extract campaign ID for error reporting
                    campaign_id = "unknown"
                    if isinstance(data, dict):
                        if "campaignId" in data:
                            campaign_id = data["campaignId"]
                        elif "data" in data and isinstance(data["data"], dict) and "campaignId" in data["data"]:
                            campaign_id = data["data"]["campaignId"]
                        elif "0" in data and isinstance(data["0"], dict) and "campaignId" in data["0"]:
                            campaign_id = data["0"]["campaignId"]
                    
                    await self.send_result(campaign_id, "", "", str(e))
                except Exception as send_error:
                    logger.error(f"Failed to send error result: {send_error}")

    async def generate_text(self, prompt: str, campaign_id: str) -> str:
        """Generate text using Gemini 2.0 Flash"""
        try:
            logger.info(f"[{campaign_id}] Starting text generation")
            
            enhanced_prompt = self._create_marketing_prompt(prompt)
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.text_model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1500,
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    stop_sequences=["\n\n---", "\n\nEND"]
                )
            )
            
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Empty response from Gemini text model")
            
            generated_text = response.candidates[0].content.parts[0].text
            
            if not generated_text or len(generated_text.strip()) < 10:
                raise ValueError("Generated text is too short or empty")
            
            logger.info(f"[{campaign_id}] Text generation completed ({len(generated_text)} chars)")
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Text generation failed: {e}")
            return f"Text generation failed: {str(e)}"

    async def generate_image(self, prompt: str, campaign_id: str) -> str:
        """Generate image using Gemini image generation"""
        try:
            logger.info(f"[{campaign_id}] Starting image generation")
            
            image_prompt = self._create_image_prompt(prompt)
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.image_model_name,
                contents=image_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    max_output_tokens=200,
                    temperature=0.8,
                    top_p=0.95
                )
            )
            
            # Process response for image
            image_path = await self._process_image_response(response, campaign_id, prompt)
            
            if image_path:
                logger.info(f"[{campaign_id}] Image generation completed: {image_path}")
                return image_path
            else:
                logger.warning(f"[{campaign_id}] No image generated, creating placeholder")
                return self._create_enhanced_placeholder(campaign_id, prompt)
                
        except Exception as e:
            logger.error(f"[{campaign_id}] Image generation failed: {e}")
            return self._create_enhanced_placeholder(campaign_id, prompt)

    async def send_result(self, campaign_id: str, generated_text: str, image_path: str, error: str = None):
        """Send result back via RabbitMQ"""
        try:
            result_data = {
                "campaignId": campaign_id,
                "generatedText": generated_text,
                "imagePath": image_path,
                "error": error
            }
            logger.warning("result_data", result_data)
            
            # NestJS microservice format with pattern and data
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
            
            # Publish directly to the result queue
            await self.channel.default_exchange.publish(
                message, routing_key=self.result_queue.name
            )
            logger.info(f"[{campaign_id}] Result sent successfully to queue: {self.result_queue.name}")
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Failed to send result: {e}")

    def _create_marketing_prompt(self, user_prompt: str) -> str:
        """Create enhanced marketing prompt"""
        return f"""
You are a world-class marketing strategist and copywriter with expertise in persuasive content creation. Your task is to transform the given prompt into compelling marketing content that drives engagement and conversions.

**ORIGINAL REQUEST:** {user_prompt}

**YOUR MISSION:** Create comprehensive marketing content that includes:

**1. ATTENTION-GRABBING HEADLINE**
- Craft a powerful, benefit-driven headline that immediately captures attention
- Use action words, emotional triggers, and clear value propositions
- Make it memorable and shareable

**2. COMPELLING DESCRIPTION**
- Write vivid, sensory-rich descriptions that paint a clear mental picture
- Use storytelling elements to create emotional connection
- Include specific details that make the content tangible and relatable
- Address pain points and position the solution naturally

**3. KEY BENEFITS & FEATURES**
- Highlight 3-5 primary benefits that matter most to the target audience
- Transform features into customer-focused benefits
- Use social proof indicators where relevant
- Create urgency or scarcity when appropriate

**4. STRATEGIC CALL-TO-ACTION**
- Provide multiple CTA options for different customer journey stages
- Use action-oriented, specific language
- Create clear next steps for engagement

Begin creating exceptional marketing content now:
"""

    def _create_image_prompt(self, user_prompt: str) -> str:
        """Create optimized image generation prompt"""
        return f"""
Create a stunning, professional-grade marketing image based on this concept: {user_prompt}

**VISUAL CONCEPT REQUIREMENTS:**
🎯 **Style & Aesthetics:**
- Premium commercial photography or high-end digital art style
- Modern, clean, and sophisticated aesthetic
- Award-winning composition with rule of thirds
- Professional color grading and balanced exposure

🎨 **Color & Lighting:**
- Vibrant yet sophisticated color palette
- Dramatic, cinematic lighting with perfect shadows and highlights
- Rich contrast and visual depth
- Colors that evoke emotion and brand trust

🌟 **Marketing Impact:**
- Emotionally compelling and aspirational
- Instantly recognizable and memorable
- Social media and advertising optimized
- Cross-platform compatible design

Generate an exceptional, commercially-viable marketing image now:
"""

    async def _process_image_response(self, response, campaign_id: str, prompt: str) -> Optional[str]:
        """Process image response and save image"""
        try:
            if not response.candidates or not response.candidates[0].content.parts:
                return None
            
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    logger.info(f"[{campaign_id}] Generated image description: {part.text[:100]}...")
                
                elif part.inline_data is not None:
                    logger.info(f"[{campaign_id}] Processing generated image data...")
                    
                    image_data = part.inline_data.data
                    image = Image.open(BytesIO(image_data))
                    
                    filename = f"campaign_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
                    image_path = self.output_dir / filename
                    
                    image.save(image_path, "PNG", optimize=True, quality=95)
                    
                    logger.info(f"[{campaign_id}] Image saved: {image_path} ({image.size[0]}x{image.size[1]})")
                    return str(image_path)
            
            return None
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Failed to process image response: {e}")
            return None

    def _create_enhanced_placeholder(self, campaign_id: str, prompt: str = "") -> str:
        """Create enhanced placeholder image"""
        try:
            img = Image.new('RGB', (1024, 1024), color='#f0f8ff')
            draw = ImageDraw.Draw(img)
            
            # Add gradient background
            for y in range(img.height):
                gradient_color = int(240 + (y / img.height) * 15)
                draw.line([(0, y), (img.width, y)], fill=(gradient_color, gradient_color + 8, 255))
            
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            # Add text
            text_lines = [
                "SOLARA AI",
                "Content Generation",
                "",
                f"Campaign: {campaign_id[:12]}",
                f"Prompt: {prompt[:40]}{'...' if len(prompt) > 40 else ''}",
                "",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ]
            
            total_height = len([line for line in text_lines if line]) * 40
            start_y = (img.height - total_height) // 2
            
            for i, line in enumerate(text_lines):
                if line:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    x = (img.width - text_width) // 2
                    y = start_y + (i * 40)
                    
                    draw.text((x + 2, y + 2), line, fill='#cccccc', font=font)
                    draw.text((x, y), line, fill='#333333', font=font)
            
            filename = f"enhanced_placeholder_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
            image_path = self.output_dir / filename
            img.save(image_path, "PNG", optimize=True)
            
            logger.info(f"[{campaign_id}] Enhanced placeholder created: {image_path}")
            return str(image_path)
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Failed to create placeholder: {e}")
            return ""

async def main():
    """Main worker function"""
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
                await asyncio.sleep(30)  # Health check every 30 seconds
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
            if hasattr(worker, 'connection') and not worker.connection.is_closed:
                await worker.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

if __name__ == "__main__":
    asyncio.run(main())
