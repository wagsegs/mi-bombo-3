import logging
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


def initialize(api_key: str) -> None:
    """Initialize Gemini API."""
    try:
        genai.configure(api_key=api_key)
        logger.info("✓ Gemini API initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Gemini API: {e}")
        raise


async def generate_text(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """
    Generate text using Gemini.
    
    Args:
        prompt: The user prompt
        system_instruction: Optional system instruction for the model
    
    Returns:
        Generated text or None if failed
    """
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate text: {e}")
        return None


async def generate_image(prompt: str) -> Optional[str]:
    """
    Generate an image using Gemini (currently uses text-to-image).
    
    Note: Gemini text models don't generate images directly.
    This is a placeholder for future image generation integration.
    You may need to use a separate service like DALL-E or Stable Diffusion.
    
    Args:
        prompt: The image prompt
    
    Returns:
        Image URL or None if failed
    """
    try:
        # Placeholder implementation
        logger.warning("Image generation not yet implemented. Placeholder used.")
        return None
    except Exception as e:
        logger.error(f"Failed to generate image: {e}")
        return None


async def generate_newspaper_data(messages: list) -> Optional[str]:
    """
    Generate newspaper data from messages.
    
    Args:
        messages: List of message dictionaries
    
    Returns:
        JSON string with newspaper data or None if failed
    """
    message_texts = "\n".join([
        f"[{msg['created_at']}] {msg['username']}: {msg['content']}"
        for msg in messages if msg['content']
    ])

    prompt = f"""Based on these Discord messages from the last 24 hours, create a newspaper summary.

Messages:
{message_texts}

Return a JSON object with these exact fields:
{{
    "headline": "A catchy, movie studio themed headline",
    "summary": "2-3 sentence overview of today's events",
    "funniest_moments": "The most hilarious/memorable moments from chat",
    "lore_updates": "Any interesting story developments or plot points",
    "cast_candidates": "Notable active members today",
    "image_prompt": "A 1940s black & white newspaper aesthetic prompt with dramatic headlines and movie studio vibes"
}}

Make it entertaining and themed around a movie studio called 'MI BOMBO Studios'.
Return ONLY valid JSON, no markdown or extra text."""

    result = await generate_text(prompt)
    return result


async def generate_weekly_cast_data(messages: list) -> Optional[str]:
    """
    Generate weekly cast data from messages.
    
    Args:
        messages: List of message dictionaries from the past week
    
    Returns:
        JSON string with cast data or None if failed
    """
    message_texts = "\n".join([
        f"{msg['username']} (@{msg['user_id']}): {msg['content']}"
        for msg in messages if msg['content']
    ])

    system_instruction = """Never depict real Discord users as recognizable real people. 
Create original anime-style fictional characters inspired only by their chat behavior.
Focus on personality traits, communication style, and presence in conversations."""

    prompt = f"""Based on this week's Discord conversations, select 5-7 standout members.

Messages:
{message_texts}

For each member, identify:
- Discord nickname and username
- Why they were selected (their role/impact)
- A personality-based character description (e.g., "Chaotic", "Serious", "Sleep-deprived", "Debater", "Gremlin", "Wholesome")

Return a JSON object:
{{
    "main_cast": [
        {{
            "nickname": "display name",
            "username": "discord username",
            "position": "their role (e.g., protagonist, support, comic relief)",
            "character_description": "personality-based description",
            "reason": "why they were selected"
        }}
    ],
    "anime_style": "one of: JoJo, Ghibli, Bleach, Cowboy Bebop, Chainsaw Man, Persona, Violet Evergarden",
    "anime_prompt": "detailed prompt for generating anime poster with these characters, their positions, and personalities"
}}

Return ONLY valid JSON, no markdown."""

    result = await generate_text(prompt, system_instruction=system_instruction)
    return result


async def generate_lore_update(messages: list) -> Optional[str]:
    """
    Generate lore updates from messages.
    
    Args:
        messages: List of message dictionaries
    
    Returns:
        Lore update text or None if failed
    """
    message_texts = "\n".join([
        f"{msg['username']}: {msg['content']}"
        for msg in messages if msg['content']
    ])

    prompt = f"""Based on these Discord messages, write a short lore update for the MI BOMBO Studios universe.
Focus on character development, relationships, and ongoing storylines.

Messages:
{message_texts}

Write 2-3 paragraphs capturing the essence of what happened in the lore. Make it dramatic and cinematic."""

    result = await generate_text(prompt)
    return result
