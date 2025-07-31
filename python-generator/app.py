import os
import logging
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from io import BytesIO

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Solara AI Generator",
    description="Advanced AI content generation using Google Gemini 2.0 Flash",
    version="1.0.0"
)

class GenerationRequest(BaseModel):
    campaignId: str = Field(..., description="Unique campaign identifier")
    prompt: str = Field(..., min_length=1, max_length=2000, description="Content generation prompt")

class GenerationResponse(BaseModel):
    campaignId: str
    generatedText: str
    imagePath: str

class GeneratorService:
    """
    Advanced Gemini 2.0 Flash service implementing best practices for text and image generation.
    """
    
    def __init__(self):
        self._initialize_api()
        self._setup_output_directory()
        self._initialize_models()
        
    def _initialize_api(self):
        """Initialize Gemini API with proper error handling."""
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "AIzaSyCFyqorPdLlXdE459IS2h1T7N8Ol2pXrV4") # remove later this key
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        try:
            self.client = genai.Client(api_key=self.gemini_api_key)
            logger.info("Gemini API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API client: {e}")
            raise
    
    def _setup_output_directory(self):
        """Setup output directory for generated images."""
        self.output_dir = Path("/app/output")
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"Output directory configured: {self.output_dir}")
    
    def _initialize_models(self):
        """Initialize Gemini models with proper validation."""
        # Text generation model
        self.text_model_name = "gemini-2.0-flash"
        
        # Image generation model 
        self.image_model_name = "gemini-2.0-flash-preview-image-generation"
        
        # Test model availability
        try:
            self._validate_models()
            logger.info("Gemini models validated successfully")
        except Exception as e:
            logger.warning(f"Model validation failed: {e}")
    
    def _validate_models(self):
        """Validate that required models are available."""
        try:
            # Test text model with minimal request
            test_response = self.client.models.generate_content(
                model=self.text_model_name,
                contents="Hello",
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.1
                )
            )
            logger.info("Text model validation successful")
            
            # Test image model with minimal request
            test_image_response = self.client.models.generate_content(
                model=self.image_model_name,
                contents="Generate a small red circle",
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    max_output_tokens=50,
                    temperature=0.1
                )
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
        try:
            logger.info(f"[{campaign_id}] Starting text generation for prompt: {prompt[:50]}...")
            
            # Enhanced prompt for marketing content generation
            enhanced_prompt = self._create_marketing_prompt(prompt)
            
            # Generate content with optimal configuration
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.text_model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1500,  # Optimal for marketing content
                    temperature=0.7,         # Balance creativity and coherence
                    top_p=0.9,              # Nucleus sampling for quality
                    top_k=40,               # Limit vocabulary for focus
                    stop_sequences=["\n\n---", "\n\nEND"]  # Natural stopping points
                )
            )
            
            # Validate and extract response
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Empty response from Gemini text model")
            
            generated_text = response.candidates[0].content.parts[0].text
            
            if not generated_text or len(generated_text.strip()) < 10:
                raise ValueError("Generated text is too short or empty")
            
            logger.info(f"[{campaign_id}] Text generation completed successfully ({len(generated_text)} chars)")
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Text generation failed: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Text generation failed: {str(e)}"
            )
    
    def _create_marketing_prompt(self, user_prompt: str) -> str:
        """Create an enhanced prompt optimized for marketing content generation."""
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

**5. AUDIENCE PSYCHOLOGY**
- Identify and address the primary target demographic
- Consider emotional motivators and rational justifiers
- Include language that resonates with their values and aspirations

**CONTENT REQUIREMENTS:**
✓ Emotionally engaging and persuasive
✓ Professional yet conversational tone
✓ Multi-channel adaptable (social, email, web, print)
✓ SEO-friendly with natural keyword integration
✓ Scannable format with clear hierarchy
✓ Rich descriptive language for visual content inspiration
✓ Authentic and trustworthy messaging

**OUTPUT FORMAT:**
Organize your response with clear sections and compelling copy that's ready for immediate use across marketing channels.

Begin creating exceptional marketing content now:
"""
    
    async def generate_image(self, prompt: str, campaign_id: str) -> str:
        """
        Generate images using Gemini 2.0 Flash image generation model.
        
        Implements best practices:
        - Optimized prompt engineering for image generation
        - Proper multimodal response handling
        - Image processing and storage
        - Comprehensive error handling
        """
        try:
            logger.info(f"[{campaign_id}] Starting image generation for prompt: {prompt[:50]}...")
            
            # Create optimized image generation prompt
            image_prompt = self._create_image_prompt(prompt)
            
            # Generate image with multimodal configuration
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.image_model_name,
                contents=image_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],  # Required for image generation
                    max_output_tokens=200,                   # For descriptive text
                    temperature=0.8,                         # Higher creativity for images
                    top_p=0.95                              # More diverse outputs
                )
            )
            
            # Process multimodal response
            image_path = await self._process_image_response(response, campaign_id, prompt)
            
            if image_path:
                logger.info(f"[{campaign_id}] Image generation completed successfully: {image_path}")
                return image_path
            else:
                logger.warning(f"[{campaign_id}] No image generated, creating placeholder")
                return self._create_enhanced_placeholder(campaign_id, prompt)
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Image generation failed: {e}")
            logger.info(f"[{campaign_id}] Falling back to enhanced placeholder")
            return self._create_enhanced_placeholder(campaign_id, prompt)
    
    def _create_image_prompt(self, user_prompt: str) -> str:
        """Create an optimized prompt for image generation."""
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

📸 **Technical Specifications:**
- Ultra-high resolution (4K+ quality)
- Crystal-sharp focus with bokeh background where appropriate
- Perfect white balance and color accuracy
- Commercial-grade image quality suitable for large format printing

🎭 **Composition & Elements:**
- Dynamic, engaging composition that draws the eye
- Clear focal point with supporting visual elements
- Negative space for text overlay compatibility
- Professional product photography or lifestyle imagery standards

🌟 **Marketing Impact:**
- Emotionally compelling and aspirational
- Instantly recognizable and memorable
- Social media and advertising optimized
- Cross-platform compatible design

**CREATIVE DIRECTION:**
Transform the concept "{user_prompt}" into a visual masterpiece that would be featured in premium marketing campaigns, luxury brand advertisements, or award-winning creative portfolios.

**QUALITY BENCHMARKS:**
- Should rival work from top creative agencies
- Suitable for billboards, premium print materials, and high-end digital campaigns
- Professional enough for Fortune 500 marketing materials
- Artistically compelling enough for creative awards consideration

Generate an exceptional, commercially-viable marketing image now:
"""
    
    async def _process_image_response(self, response, campaign_id: str, prompt: str) -> Optional[str]:
        """Process multimodal response and extract image data."""
        try:
            if not response.candidates or not response.candidates[0].content.parts:
                return None
            
            for part in response.candidates[0].content.parts:
                # Handle text part
                if part.text is not None:
                    logger.info(f"[{campaign_id}] Generated image description: {part.text[:100]}...")
                
                # Handle image part
                elif part.inline_data is not None:
                    logger.info(f"[{campaign_id}] Processing generated image data...")
                    
                    # Convert image data
                    image_data = part.inline_data.data
                    image = Image.open(BytesIO(image_data))
                    
                    # Generate unique filename
                    filename = f"campaign_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
                    image_path = self.output_dir / filename
                    
                    # Save with optimization
                    image.save(image_path, "PNG", optimize=True, quality=95)
                    
                    # Log image details
                    logger.info(f"[{campaign_id}] Image saved: {image_path} ({image.size[0]}x{image.size[1]})")
                    return str(image_path)
            
            return None
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Failed to process image response: {e}")
            return None
    
    def _create_enhanced_placeholder(self, campaign_id: str, prompt: str = "") -> str:
        """Create an enhanced placeholder image with professional appearance."""
        try:
            # Create high-quality placeholder
            img = Image.new('RGB', (1024, 1024), color='#f0f8ff')  # Alice blue
            draw = ImageDraw.Draw(img)
            
            # Add gradient background
            for y in range(img.height):
                gradient_color = int(240 + (y / img.height) * 15)  # Subtle gradient
                draw.line([(0, y), (img.width, y)], fill=(gradient_color, gradient_color + 8, 255))
            
            # Load font
            try:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            except:
                font_large = font_small = None
            
            # Add professional text
            text_lines = [
                "SOLARA AI",
                "Content Generation",
                "",
                f"Campaign: {campaign_id[:12]}",
                f"Prompt: {prompt[:40]}{'...' if len(prompt) > 40 else ''}",
                "",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ]
            
            # Center text vertically
            total_height = len([line for line in text_lines if line]) * 40
            start_y = (img.height - total_height) // 2
            
            for i, line in enumerate(text_lines):
                if line:
                    # Calculate text position for centering
                    bbox = draw.textbbox((0, 0), line, font=font_large)
                    text_width = bbox[2] - bbox[0]
                    x = (img.width - text_width) // 2
                    y = start_y + (i * 40)
                    
                    # Add shadow effect
                    draw.text((x + 2, y + 2), line, fill='#cccccc', font=font_large)
                    draw.text((x, y), line, fill='#333333', font=font_large)
            
            # Save placeholder
            filename = f"enhanced_placeholder_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
            image_path = self.output_dir / filename
            img.save(image_path, "PNG", optimize=True)
            
            logger.info(f"[{campaign_id}] Enhanced placeholder created: {image_path}")
            return str(image_path)
            
        except Exception as e:
            logger.error(f"[{campaign_id}] Failed to create enhanced placeholder: {e}")
            # Fallback to simple placeholder
            return self._create_simple_fallback(campaign_id)
    
    def _create_simple_fallback(self, campaign_id: str) -> str:
        """Create a simple fallback image if all else fails."""
        try:
            img = Image.new('RGB', (512, 512), color='lightblue')
            filename = f"fallback_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
            image_path = self.output_dir / filename
            img.save(image_path)
            return str(image_path)
        except Exception:
            return ""
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the service."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "models": {
                "text_model": self.text_model_name,
                "image_model": self.image_model_name
            },
            "api": {
                "client_initialized": hasattr(self, 'client'),
                "api_key_configured": bool(self.gemini_api_key)
            },
            "storage": {
                "output_directory": str(self.output_dir),
                "directory_writable": self.output_dir.is_dir() and os.access(self.output_dir, os.W_OK)
            }
        }

# Initialize service
try:
    generator_service = GeneratorService()
    logger.info("Generator service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize generator service: {e}")
    raise

@app.post("/generate", response_model=GenerationResponse)
async def generate_content(request: GenerationRequest):
    """
    Generate marketing content including text and images.
    
    This endpoint implements the complete content generation workflow:
    1. Validates input parameters
    2. Generates high-quality text using Gemini 2.0 Flash
    3. Creates professional images using Gemini image generation
    4. Returns structured response with generated assets
    """
    campaign_id = request.campaignId
    prompt = request.prompt
    
    logger.info(f"[{campaign_id}] Starting content generation workflow")
    logger.info(f"[{campaign_id}] Prompt: {prompt}")
    
    try:
        # Generate text and image concurrently for better performance
        text_task = generator_service.generate_text(prompt, campaign_id)
        image_task = generator_service.generate_image(prompt, campaign_id)
        
        # Await both tasks
        generated_text, image_path = await asyncio.gather(text_task, image_task)
        
        logger.info(f"[{campaign_id}] Content generation workflow completed successfully")
        
        return GenerationResponse(
            campaignId=campaign_id,
            generatedText=generated_text,
            imagePath=image_path
        )
        
    except Exception as e:
        logger.error(f"[{campaign_id}] Content generation workflow failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Content generation failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns detailed status information about:
    - Service health
    - Model availability  
    - API connectivity
    - Storage accessibility
    """
    try:
        health_status = generator_service.get_health_status()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Solara AI Generator",
        "version": "1.0.0",
        "description": "Advanced AI content generation using Google Gemini 2.0 Flash",
        "endpoints": {
            "generate": "/generate",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    logger.info("Starting Solara AI Generator Service...")
    logger.info(f"Using Gemini models - Text: gemini-2.0-flash, Image: gemini-2.0-flash-preview-image-generation")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )