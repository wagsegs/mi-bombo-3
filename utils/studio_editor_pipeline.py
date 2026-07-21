import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import tracking
from ai import text_provider
from config import CHUNK_SIZE_MESSAGES, MAX_PROMPT_CHARS, TARGET_INPUT_TOKENS
from database import get_conversation_detail, get_conversation_summaries_between

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4))


def _message_to_prompt_line(message: Dict[str, Any]) -> str:
    created_at = message.get('created_at')
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    return f"[{created_at}] {message.get('username', 'Unknown')}: {message.get('content', '')}"


def _format_prompt(messages: List[Dict[str, Any]]) -> str:
    return "\n".join([
        _message_to_prompt_line(msg)
        for msg in messages if msg.get('content')
    ])


def _max_budget_chars() -> int:
    return min(MAX_PROMPT_CHARS, TARGET_INPUT_TOKENS * 4)


def _within_budget(prompt_text: str) -> bool:
    tokens = _estimate_tokens(prompt_text)
    return len(prompt_text) <= MAX_PROMPT_CHARS and tokens <= TARGET_INPUT_TOKENS


def _split_text_into_segments(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    segments: List[str] = []
    current: List[str] = []
    current_len = 0
    for word in words:
        delimiter = 1 if current else 0
        if current_len + len(word) + delimiter > max_chars:
            if current:
                segments.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + delimiter

    if current:
        segments.append(" ".join(current))
    return segments


def _split_long_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = message.get('content', '')
    if not content:
        return [message]

    overhead = len(_message_to_prompt_line({
        'created_at': message.get('created_at'),
        'username': message.get('username', 'Unknown'),
        'content': '',
    }))
    max_chars = max(1, _max_budget_chars() - overhead - 50)
    segments = _split_text_into_segments(content, max_chars)

    if len(segments) == 1:
        return [message]

    split_messages: List[Dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        split_messages.append({
            **message,
            'content': segment,
            'content_segment_index': index,
        })

    logger.warning(
        "Studio Editor Pipeline: split single oversized message from conversation %s into %s segments.",
        message.get('conversation_id', 'unknown'),
        len(split_messages),
    )
    return split_messages


def _split_messages_to_budget(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    if not messages:
        return []

    safe_messages: List[Dict[str, Any]] = []
    for message in messages:
        prompt_line = _message_to_prompt_line(message)
        if len(prompt_line) > _max_budget_chars() or not _within_budget(prompt_line):
            split_messages = _split_long_message(message)
            safe_messages.extend(split_messages)
        else:
            safe_messages.append(message)

    chunks: List[List[Dict[str, Any]]] = []
    current_chunk: List[Dict[str, Any]] = []
    for message in safe_messages:
        candidate = current_chunk + [message]
        prompt_text = _format_prompt(candidate)

        if _within_budget(prompt_text):
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)
        if _within_budget(_format_prompt([message])):
            current_chunk = [message]
            continue

        logger.warning(
            "Studio Editor Pipeline: recursive chunk split required for message %s.",
            message.get('conversation_id', 'unknown'),
        )
        split_messages = _split_long_message(message)
        for split_message in split_messages:
            if _within_budget(_format_prompt([split_message])):
                chunks.append([split_message])
            else:
                logger.warning(
                    "Studio Editor Pipeline: single split segment still exceeds budget for message %s. Sending smallest possible segment.",
                    message.get('conversation_id', 'unknown'),
                )
                chunks.append([split_message])
        current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _calculate_average_gap(messages: List[Dict[str, Any]]) -> float:
    timestamps = [msg.get('created_at') for msg in messages if msg.get('created_at') is not None]
    timestamps = [ts for ts in timestamps if isinstance(ts, datetime)]
    timestamps.sort()
    if len(timestamps) <= 1:
        return 0.0
    gaps = [
        (timestamps[idx] - timestamps[idx - 1]).total_seconds()
        for idx in range(1, len(timestamps))
    ]
    return sum(gaps) / len(gaps) if gaps else 0.0


async def get_eligible_conversations(start_time: datetime, end_time: datetime, limit: int = 50) -> List[Dict[str, Any]]:
    conversation_summaries = await get_conversation_summaries_between(start_time, end_time, limit)
    eligible: List[Dict[str, Any]] = []

    for conv in conversation_summaries:
        detail = await get_conversation_detail(conv['id'])
        if not detail:
            continue

        messages = detail.get('messages', []) or []
        message_count = detail.get('message_count', len(messages))
        participant_count = len(detail.get('participant_ids') or [])
        started_at = detail.get('started_at')
        ended_at = detail.get('ended_at')
        duration_seconds = 0
        if started_at and ended_at:
            duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
        average_gap_seconds = _calculate_average_gap(messages)

        is_eligible, reasons = tracking.evaluate_lore_eligibility(
            message_count=message_count,
            participant_count=participant_count,
            duration_seconds=duration_seconds,
            average_gap_seconds=average_gap_seconds,
        )

        if not is_eligible:
            logger.info(
                "Studio Editor Pipeline: conversation %s excluded from newspaper: %s",
                conv['id'],
                reasons,
            )
            continue

        eligible.append(detail)

    logger.info("Studio Editor Pipeline: Eligible conversations=%s", len(eligible))
    return eligible


async def _generate_text_with_budget(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    logger.info(
        "Studio Editor Pipeline: Groq request size check: Characters=%s, Estimated tokens=%s",
        len(prompt),
        _estimate_tokens(prompt),
    )
    if not _within_budget(prompt):
        logger.warning(
            "Studio Editor Pipeline: Groq request exceeds budget and will not be sent: Characters=%s, Estimated tokens=%s",
            len(prompt),
            _estimate_tokens(prompt),
        )
        return None

    return await text_provider.generate_text(prompt, system_instruction=system_instruction, conversational=False)


def _merge_summary_jsons(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = {
        "events": [],
        "running_jokes": [],
        "important_quotes": [],
        "main_characters": [],
        "lore": [],
        "importance": 0,
    }
    for summary in summaries:
        for field, value in summary.items():
            if field == "importance":
                merged["importance"] = max(merged["importance"], value or 0)
            elif isinstance(value, list):
                merged[field].extend(value)
    return merged


async def _summarize_messages_recursively(messages: List[Dict[str, Any]], conversation_id: int, chunk_index: str) -> Optional[Dict[str, Any]]:
    prompt_text = _format_prompt(messages)
    if not prompt_text:
        return None

    system_instruction = (
        "You are a Studio Editor summarizing a split conversation chunk for MI BOMBO Studios. "
        "Return only valid JSON with a structured summary."
    )
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

    if _within_budget(prompt):
        logger.info(
            "Studio Editor Pipeline: safe Groq request for conversation %s chunk %s: Characters=%s, Estimated tokens=%s",
            conversation_id,
            chunk_index,
            len(prompt),
            _estimate_tokens(prompt),
        )
        summary_json = await _generate_text_with_budget(prompt, system_instruction=system_instruction)
        if not summary_json:
            return None
        try:
            return json.loads(summary_json)
        except Exception as exc:
            logger.exception("Studio Editor Pipeline: invalid JSON from conversation %s chunk %s: %s", conversation_id, chunk_index, exc)
            return None

    logger.warning(
        "Studio Editor Pipeline: oversized Groq chunk detected for conversation %s chunk %s. Recursively splitting messages.",
        conversation_id,
        chunk_index,
    )
    sub_chunks = _split_messages_to_budget(messages)
    if len(sub_chunks) == 1 and len(sub_chunks[0]) == len(messages):
        logger.warning(
            "Studio Editor Pipeline: could not split conversation %s chunk %s into smaller safe chunks. Falling back to smallest possible segment.",
            conversation_id,
            chunk_index,
        )
        split_messages = _split_long_message(messages[0]) if len(messages) == 1 else messages
        sub_chunks = [[msg] for msg in split_messages]

    summaries = []
    for idx, sub_chunk in enumerate(sub_chunks, start=1):
        sub_index = f"{chunk_index}.{idx}"
        result = await _summarize_messages_recursively(sub_chunk, conversation_id, sub_index)
        if result:
            summaries.append(result)

    if not summaries:
        return None
    return _merge_summary_jsons(summaries)


async def summarize_conversation_chunk(messages: List[Dict[str, Any]], conversation_id: int, chunk_index: int) -> Optional[Dict[str, Any]]:
    prompt_text = _format_prompt(messages)
    characters = len(prompt_text)
    tokens = _estimate_tokens(prompt_text)
    logger.info(
        "Studio Editor Pipeline: Conversation %s chunk %s: Messages=%s, Characters=%s, Estimated tokens=%s",
        conversation_id,
        chunk_index,
        len(messages),
        characters,
        tokens,
    )

    if characters == 0:
        return None

    summary_data = await _summarize_messages_recursively(messages, conversation_id, str(chunk_index))
    if not summary_data:
        logger.warning("Studio Editor Pipeline: conversation %s chunk %s summary failed", conversation_id, chunk_index)
        return None

    return {
        "conversation_id": conversation_id,
        "chunk_index": chunk_index,
        "summary": summary_data,
        "message_count": len(messages),
        "characters": characters,
        "estimated_tokens": tokens,
    }


async def summarize_conversation(detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conversation_id = detail.get('id')
    messages = detail.get('messages', []) or []

    if not messages:
        logger.warning("Studio Editor Pipeline: conversation %s has no messages", conversation_id)
        return None

    chunks = _split_messages_to_budget(messages)
    logger.info(
        "Studio Editor Pipeline: conversation %s: Messages=%s, Chunks=%s",
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

    merged_summary = {
        "events": [],
        "running_jokes": [],
        "important_quotes": [],
        "main_characters": [],
        "lore": [],
        "importance": 0,
    }
    merged = {
        "conversation_id": conversation_id,
        "channel_name": detail.get('channel_name'),
        "started_at": detail.get('started_at').isoformat() if isinstance(detail.get('started_at'), datetime) else detail.get('started_at'),
        "ended_at": detail.get('ended_at').isoformat() if isinstance(detail.get('ended_at'), datetime) else detail.get('ended_at'),
        "message_count": len(messages),
        "participant_count": len(detail.get('participant_ids') or []),
        "conversation_summary": merged_summary,
        "chunks": chunk_summaries,
    }

    for entry in chunk_summaries:
        summary = entry['summary']
        for field, value in summary.items():
            if field == 'importance':
                merged_summary['importance'] = max(merged_summary['importance'], value or 0)
            elif isinstance(value, list):
                merged_summary[field].extend(value)

    logger.info(
        "Studio Editor Pipeline: conversation %s merged summary: total_chunks=%s, total_messages=%s",
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


def _build_newspaper_prompt(conversation_summaries: List[Dict[str, Any]]) -> str:
    summary_payload = json.dumps(conversation_summaries, indent=2, default=str)
    return f"""Based on these eligible conversation summaries from MI BOMBO Studios, create a newspaper summary that captures the day's memorable studio moments.

Conversation summaries:
{summary_payload}

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

Make it entertaining, dramatic, and themed around MI BOMBO Studios.
Return ONLY valid JSON, no markdown or extra text."""


def _trim_conversation_summaries_to_budget(conversation_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trimmed = list(conversation_summaries)
    prompt = _build_newspaper_prompt(trimmed)
    while trimmed and (len(prompt) > MAX_PROMPT_CHARS or _estimate_tokens(prompt) > TARGET_INPUT_TOKENS):
        logger.warning(
            "Studio Editor Pipeline: final newspaper prompt exceeds budget: characters=%s, tokens=%s. Trimming one conversation summary.",
            len(prompt),
            _estimate_tokens(prompt),
        )
        trimmed.pop()
        prompt = _build_newspaper_prompt(trimmed)
    return trimmed


async def generate_final_newspaper_json(conversation_summaries: List[Dict[str, Any]]) -> Optional[str]:
    if not conversation_summaries:
        logger.warning("Studio Editor Pipeline: no conversation summaries available for final newspaper generation.")
        return None

    trimmed = _trim_conversation_summaries_to_budget(conversation_summaries)
    if not trimmed:
        logger.error("Studio Editor Pipeline: unable to keep final newspaper prompt within budget after trimming.")
        return None

    prompt = _build_newspaper_prompt(trimmed)
    prompt_chars = len(prompt)
    prompt_tokens = _estimate_tokens(prompt)
    logger.info(
        "Studio Editor Pipeline: Final newspaper input: Conversations=%s, Characters=%s, Estimated tokens=%s",
        len(trimmed),
        prompt_chars,
        prompt_tokens,
    )

    result = await _generate_text_with_budget(prompt)
    if result is not None:
        return result

    logger.warning(
        "Studio Editor Pipeline: final newspaper prompt still exceeds budget after trimming. Applying aggressive trimming."
    )
    aggressive = list(trimmed)
    while aggressive:
        aggressive.pop()
        attempt_prompt = _build_newspaper_prompt(aggressive)
        if _within_budget(attempt_prompt):
            logger.info(
                "Studio Editor Pipeline: aggressive final newspaper prompt now safe with %s conversations.",
                len(aggressive),
            )
            return await _generate_text_with_budget(attempt_prompt)

    logger.error("Studio Editor Pipeline: unable to create a safe final newspaper Groq request.")
    return None
