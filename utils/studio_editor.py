import json
import logging
from typing import Any, Dict, List, Optional

from ai import text_provider
from config import CHUNK_SIZE_MESSAGES, MAX_PROMPT_CHARS, TARGET_INPUT_TOKENS
from database import get_conversation_detail

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4))


def _chunk_messages(messages: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    if not messages:
        return []
    chunks = []
    for i in range(0, len(messages), chunk_size):
        chunks.append(messages[i:i + chunk_size])
    return chunks


def _format_chunk_prompt(messages: List[Dict[str, Any]]) -> str:
    return "\n".join([
        f"[{msg['created_at']}] {msg['username']}: {msg['content']}"
        for msg in messages if msg.get('content')
    ])


async def summarize_conversation_chunk(messages: List[Dict[str, Any]], conversation_id: int, chunk_index: int) -> Optional[Dict[str, Any]]:
    prompt_text = _format_chunk_prompt(messages)
    characters = len(prompt_text)
    tokens = _estimate_tokens(prompt_text)
    logger.info(
        "Conversation %s chunk %s: Messages=%s, Characters=%s, Estimated tokens=%s",
        conversation_id,
        chunk_index,
        len(messages),
        characters,
        tokens,
    )

    if characters == 0:
        return None

    system_instruction = """You are a Studio Editor summarizing a split conversation chunk for MI BOMBO Studios. Return only valid JSON with a structured summary."""
    prompt = f"""Conversation chunk from MI BOMBO Studios:

Messages:
{prompt_text}

Return a JSON object with these exact fields:
{{
    "events": [],
    "running_jokes": [],
    "important_quotes": [],
    "main_characters": [],
    "lore": [],
    "importance": 0
}}

Focus on memorable moments, dramatic beats, and studio-themed events. Return ONLY valid JSON."""
    summary_json = await text_provider.generate_text(prompt, system_instruction=system_instruction, conversational=False)
    if not summary_json:
        logger.warning("Conversation %s chunk %s summary failed", conversation_id, chunk_index)
        return None

    try:
        data = json.loads(summary_json)
    except Exception as exc:
        logger.exception("Invalid JSON from conversation %s chunk %s: %s", conversation_id, chunk_index, exc)
        return None

    return {
        "conversation_id": conversation_id,
        "chunk_index": chunk_index,
        "summary": data,
        "message_count": len(messages),
        "characters": characters,
        "estimated_tokens": tokens,
    }


async def summarize_conversation(conversation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conversation_id = conversation.get('id')
    detail = await get_conversation_detail(conversation_id)
    if not detail:
        logger.warning("Conversation %s detail not found", conversation_id)
        return None

    messages = detail.get('messages', [])
    if not messages:
        logger.warning("Conversation %s has no messages", conversation_id)
        return None

    chunk_size = CHUNK_SIZE_MESSAGES
    chunks = _chunk_messages(messages, chunk_size)
    logger.info(
        "Conversation %s: Messages=%s, Chunks=%s",
        conversation_id,
        len(messages),
        len(chunks),
    )

    chunk_summaries = []
    for index, chunk in enumerate(chunks, start=1):
        summary = await summarize_conversation_chunk(chunk, conversation_id, index)
        if summary:
            chunk_summaries.append(summary)

    if not chunk_summaries:
        return None

    merged = {
        "conversation_id": conversation_id,
        "conversation_summary": {
            "events": [],
            "running_jokes": [],
            "important_quotes": [],
            "main_characters": [],
            "lore": [],
            "importance": 0,
        },
        "chunks": [],
    }

    for entry in chunk_summaries:
        summary = entry['summary']
        merged['chunks'].append(entry)
        for field in merged['conversation_summary']:
            if field == 'importance':
                merged['conversation_summary'][field] = max(
                    merged['conversation_summary'][field],
                    summary.get(field, 0) or 0,
                )
            elif isinstance(summary.get(field), list):
                merged['conversation_summary'][field].extend(summary.get(field) or [])

    logger.info(
        "Conversation %s merged summary: total_chunks=%s, total_messages=%s",
        conversation_id,
        len(chunk_summaries),
        len(messages),
    )
    return merged


async def summarize_conversations(conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summaries = []
    for conversation in conversations:
        result = await summarize_conversation(conversation)
        if result:
            summaries.append(result)
    return summaries
