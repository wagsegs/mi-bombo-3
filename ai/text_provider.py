import json
import logging
import os
from typing import Optional

from groq import AsyncGroq

logger = logging.getLogger(__name__)

# Initialize Groq client
_groq_client = None


def _get_groq_client() -> Optional[AsyncGroq]:
    """Get or create the Groq client."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("Missing GROQ_API_KEY environment variable")
            return None
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


async def generate_text(prompt: str, system_instruction: Optional[str] = None, *, conversational: bool = False) -> Optional[str]:
    """Generate text through Groq."""
    if conversational:
        enabled = os.getenv("AI_CHAT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        if not enabled:
            logger.warning("Conversational text generation is disabled")
            return None

    client = _get_groq_client()
    if not client:
        logger.error("Groq client is not available")
        return None

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
        )
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        return None
    except Exception as exc:
        logger.error("Groq text generation failed: %s", exc)
        return None


async def generate_conversational_reply(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    return await generate_text(prompt, system_instruction=system_instruction, conversational=True)


async def generate_newspaper_data(messages: list) -> Optional[str]:
    message_texts = "\n".join([
        f"[{msg['created_at']}] {msg['username']}: {msg['content']}"
        for msg in messages if msg['content']
    ])

    prompt = f"""Based on these Discord messages from the last 24 hours, create a newspaper summary for MI BOMBO Studios.

Messages:
{message_texts}

Focus on:
- Funniest moments and memorable jokes
- Running jokes and community memes
- Unexpected events or chaotic moments
- Notable arguments or dramatic interactions
- "Main character" moments
- Community lore developments

Ignore:
- Private conversations
- Emotional support discussions
- Personal life updates
- Generic chatting
- Boring filler

Return a JSON object with these exact fields:
{{
    "headline": "A catchy, dramatic movie studio themed headline (e.g., 'CHAOS ERUPTS ON SET', 'DIRECTOR MISSING IN ACTION', 'STUDIO IN PANIC')",
    "summary": "2-3 dramatic sentences capturing today's most memorable events",
    "funniest_moments": "The most hilarious/memorable moments from chat",
    "lore_updates": "Any interesting story developments or plot points",
    "cast_candidates": "Notable active members who made an impact today",
    "image_prompt": "A detailed, cinematic prompt for a 1940s black & white newspaper front page. Include: dramatic typography, film grain texture, vintage newspaper layout, movie studio headline, dramatic photography style, old Hollywood aesthetic, cinematic lighting. The scene should feel like a dramatic moment from a golden age film studio. Focus on visual storytelling through newspaper design."
}}

Make it entertaining, dramatic, and themed around a movie studio called 'MI BOMBO Studios'.
Return ONLY valid JSON, no markdown or extra text."""

    return await generate_text(prompt, conversational=False)


async def generate_weekly_cast_data(messages: list) -> Optional[str]:
    message_texts = "\n".join([
        f"{msg['username']} (@{msg['user_id']}): {msg['content']}"
        for msg in messages if msg['content']
    ])

    system_instruction = """You are casting an anime series based on Discord chat behavior. Never depict real Discord users as recognizable real people.
Create original anime-style fictional characters inspired ONLY by their chat behavior, personality, communication style, and presence in conversations.
Focus on personality traits like: Chaotic, Serious, Sleep-deprived, Debater, Gremlin, Wholesome, Sarcastic, Energetic, Mysterious, etc.
Never use appearance-based descriptions. Always use personality-based character descriptions."""

    prompt = f"""Based on this week's Discord conversations, select 5-7 standout members based on their IMPACT, not message count.

Look for:
- Funniest member
- Villain of the week
- Accidental protagonist
- Chaos gremlin
- Smartest comeback
- Biggest plot twist
- Side character becoming important
- Running joke starter
- Most dramatic moments

Messages:
{message_texts}

For each selected member, identify:
- Discord nickname and username
- Why they were selected (their role/impact on the community)
- A personality-based character description (e.g., "Chaotic trickster who thrives on confusion", "Serious strategist with dry wit", "Sleep-deprived genius", "Relentless debater", "Wholesome peacemaker")

Return a JSON object:
{{
    "main_cast": [
        {{
            "nickname": "display name",
            "username": "discord username",
            "position": "their anime role (e.g., protagonist, antagonist, comic relief, strategist, wildcard, mentor, sidekick)",
            "character_description": "detailed personality-based description for anime character design",
            "reason": "why they were selected based on their impact"
        }}
    ],
    "anime_style": "one of: JoJo, Ghibli, Bleach, Cowboy Bebop, Chainsaw Man, Persona, Violet Evergarden, Demon Slayer, My Hero Academia",
    "anime_prompt": "A detailed cinematic prompt for an anime movie poster featuring all selected cast members together. Include: dynamic poses for each character based on their personalities, dramatic lighting, movie title treatment, ensemble composition, character positions that reflect their roles, the specified anime style, cinematic atmosphere. Focus on creating a cohesive group shot that feels like a real anime movie poster."
}}

Return ONLY valid JSON, no markdown."""

    return await generate_text(prompt, system_instruction=system_instruction, conversational=False)


async def generate_lore_update(messages: list) -> Optional[str]:
    message_texts = "\n".join([
        f"{msg['username']}: {msg['content']}"
        for msg in messages if msg['content']
    ])

    system_instruction = """You are writing lore episodes for a comedy series about a movie studio called MI BOMBO Studios.
Only create canon from memorable SHARED community moments. Never use personal conversations, emotional support, private discussions, or one-on-one exchanges.
Treat each lore update like an episode of a comedy anime series. Focus on: funniest moments, sarcastic moments, inside jokes, running jokes, chaotic events, unexpected interactions, iconic quotes, community memes.
Ignore: private conversations, emotional support, personal issues, generic chatting, boring filler."""

    prompt = f"""Based on these Discord messages, create a lore episode for MI BOMBO Studios.

Messages:
{message_texts}

Identify the most memorable community moments and create an episode entry.

Return a JSON object with these exact fields:
{{
    "title": "A dramatic, catchy title for this episode (e.g., 'The Great Microwave Incident', 'The Day the Director Disappeared')",
    "summary": "2-3 dramatic paragraphs capturing the essence of this episode's events",
    "lore": "The most memorable, funny, or iconic moments from this episode written as lore text",
    "image_prompt": "A detailed cinematic prompt for a single illustrated scene showing the most memorable moment from this episode. Style it like a screenshot from an animated movie. Include: the main characters, dramatic lighting, cinematic composition, animated comedy style, expressive character poses, the specific memorable moment. Focus on one scene, not a collage."
}}

Make it feel like "Episode 43" of a comedy series, not "people talked today."
Return ONLY valid JSON, no markdown."""

    return await generate_text(prompt, system_instruction=system_instruction, conversational=False)
