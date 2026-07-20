import logging
from typing import Optional

logger = logging.getLogger(__name__)


def initialize(api_key: str) -> None:
    logger.warning("Gemini support has been removed; this module is no longer used")


async def generate_text(prompt: str, system_instruction: Optional[str] = None, *, conversational: bool = False) -> Optional[str]:
    return None


async def generate_conversational_reply(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    return None


async def generate_image(prompt: str) -> Optional[str]:
    return None


async def generate_newspaper_data(messages: list) -> Optional[str]:
    return None


async def generate_weekly_cast_data(messages: list) -> Optional[str]:
    return None


async def generate_lore_update(messages: list) -> Optional[str]:
    return None
