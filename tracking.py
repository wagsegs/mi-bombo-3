import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

import database
from config import (
    LORE_MIN_PARTICIPANTS,
    LORE_MIN_MESSAGES,
    LORE_MAX_AVERAGE_REPLY_GAP_SECONDS,
    LORE_MIN_DURATION_SECONDS,
    LORE_FLEXIBLE_MESSAGE_COUNT,
    LORE_FLEXIBLE_MIN_PARTICIPANTS,
    LORE_FLEXIBLE_MIN_DURATION_SECONDS,
    LORE_FLEXIBLE_MAX_AVERAGE_REPLY_GAP_SECONDS,
)
from utils.timezone import ensure_utc_datetime, utc_now

logger = logging.getLogger(__name__)


def get_lore_eligibility_reasons(
    message_count: int,
    participant_count: int,
    duration_seconds: int,
    average_gap_seconds: float,
) -> List[str]:
    """Return the reasons a conversation should not be considered for lore."""
    reasons: List[str] = []
    if message_count < LORE_MIN_MESSAGES:
        reasons.append(f"Needs at least {LORE_MIN_MESSAGES} messages")
    if participant_count < LORE_MIN_PARTICIPANTS:
        reasons.append(f"Needs at least {LORE_MIN_PARTICIPANTS} participants")
    if average_gap_seconds > LORE_MAX_AVERAGE_REPLY_GAP_SECONDS:
        reasons.append(
            f"Replies are too spread out (max gap {LORE_MAX_AVERAGE_REPLY_GAP_SECONDS}s)"
        )
    if duration_seconds < LORE_MIN_DURATION_SECONDS:
        reasons.append(f"Needs at least {LORE_MIN_DURATION_SECONDS}s of activity")
    return reasons


def get_lore_eligibility_rule_summary() -> str:
    """Return a human-readable summary of the current configurable eligibility rules."""
    return (
        f"Configured rule: {LORE_MIN_MESSAGES}+ messages, {LORE_MIN_PARTICIPANTS}+ participants, "
        f"{LORE_MIN_DURATION_SECONDS}s minimum activity, and {LORE_MAX_AVERAGE_REPLY_GAP_SECONDS}s max average reply gap. "
        f"Highly active chats may still qualify with {LORE_FLEXIBLE_MESSAGE_COUNT}+ messages and "
        f"{LORE_FLEXIBLE_MIN_DURATION_SECONDS}s activity."
    )


def evaluate_lore_eligibility(
    message_count: int,
    participant_count: int,
    duration_seconds: int,
    average_gap_seconds: float,
) -> tuple[bool, List[str]]:
    """Return whether a conversation is eligible for lore generation and the reasons if not."""
    if (
        message_count >= LORE_MIN_MESSAGES
        and participant_count >= LORE_MIN_PARTICIPANTS
        and duration_seconds >= LORE_MIN_DURATION_SECONDS
        and average_gap_seconds <= LORE_MAX_AVERAGE_REPLY_GAP_SECONDS
    ):
        return True, []

    if (
        message_count >= LORE_FLEXIBLE_MESSAGE_COUNT
        and participant_count >= LORE_FLEXIBLE_MIN_PARTICIPANTS
        and duration_seconds >= LORE_FLEXIBLE_MIN_DURATION_SECONDS
        and average_gap_seconds <= LORE_FLEXIBLE_MAX_AVERAGE_REPLY_GAP_SECONDS
    ):
        return True, []

    reasons = get_lore_eligibility_reasons(
        message_count=message_count,
        participant_count=participant_count,
        duration_seconds=duration_seconds,
        average_gap_seconds=average_gap_seconds,
    )
    return False, reasons


class ConversationTracker:
    """
    Tracks conversations to group related messages.
    Used for lore, quote game, newspaper, and weekly cast.
    """

    def __init__(self):
        self.conversations: Dict[int, 'Conversation'] = {}

    async def track_message(
        self,
        message_id: int,
        user_id: int,
        content: str,
        channel_id: int,
        timestamp: datetime,
        reply_to: int = None,
    ) -> 'Conversation':
        """
        Track a message and group it with conversations.
        
        Args:
            message_id: Discord message ID
            user_id: Discord user ID
            content: Message content
            channel_id: Discord channel ID
            timestamp: Message timestamp
            reply_to: Message ID this is replying to
        """
        try:
            # Find or create conversation
            conv_id = self._find_or_create_conversation(
                channel_id, user_id, timestamp, reply_to
            )

            # Add message to conversation
            if conv_id in self.conversations:
                conv = self.conversations[conv_id]
                conv.add_message(message_id, user_id, content, timestamp)
                return conv
        except Exception as e:
            logger.error(f"Failed to track message {message_id}: {e}")
        return None

    def _find_or_create_conversation(
        self,
        channel_id: int,
        user_id: int,
        timestamp: datetime,
        reply_to: int = None,
    ) -> int:
        """
        Find an existing conversation or create a new one.
        
        Conversations are grouped by:
        - Channel
        - Time proximity (within 30 minutes)
        - Reply chains
        """
        normalized_timestamp = ensure_utc_datetime(timestamp) or utc_now()

        # Check if this is a reply to an existing message
        if reply_to:
            for conv_id, conv in self.conversations.items():
                if reply_to in conv.message_ids:
                    return conv_id

        # Find active conversations in this channel within 30 minutes
        time_window = normalized_timestamp - timedelta(minutes=30)
        for conv_id, conv in self.conversations.items():
            if (conv.channel_id == channel_id and
                conv.last_message_time >= time_window):
                return conv_id

        # Create new conversation
        conv_id = max(self.conversations.keys()) + 1 if self.conversations else 1
        self.conversations[conv_id] = Conversation(
            conv_id, channel_id, normalized_timestamp
        )
        return conv_id

    def get_conversations_by_topic(self, topic: str) -> List['Conversation']:
        """Get conversations matching a topic."""
        matching = []
        for conv in self.conversations.values():
            if conv.contains_topic(topic):
                matching.append(conv)
        return matching

    def get_recent_conversations(self, hours: int = 24) -> List['Conversation']:
        """Get conversations from the last N hours."""
        cutoff = utc_now() - timedelta(hours=hours)
        recent = [
            conv for conv in self.conversations.values()
            if conv.last_message_time >= cutoff
        ]
        return sorted(recent, key=lambda c: c.last_message_time, reverse=True)

    def clear_old_conversations(self, hours: int = 72) -> None:
        """Clear conversations older than N hours."""
        cutoff = utc_now() - timedelta(hours=hours)
        to_remove = [
            conv_id for conv_id, conv in self.conversations.items()
            if conv.last_message_time < cutoff
        ]
        for conv_id in to_remove:
            del self.conversations[conv_id]
        logger.info(f"Cleared {len(to_remove)} old conversations")


class Conversation:
    """Represents a grouped conversation."""

    def __init__(self, conv_id: int, channel_id: int, started_at: datetime):
        self.id = conv_id
        self.channel_id = channel_id
        self.started_at = ensure_utc_datetime(started_at) or utc_now()
        self.last_message_time = self.started_at
        self.message_ids: List[int] = []
        self.participant_ids: set = set()
        self.content: List[str] = []

    def add_message(
        self,
        message_id: int,
        user_id: int,
        content: str,
        timestamp: datetime,
    ) -> None:
        """Add a message to this conversation."""
        normalized_timestamp = ensure_utc_datetime(timestamp) or utc_now()
        self.message_ids.append(message_id)
        self.participant_ids.add(user_id)
        self.content.append(content)
        self.last_message_time = normalized_timestamp

    def contains_topic(self, topic: str) -> bool:
        """Check if conversation contains a topic."""
        topic_lower = topic.lower()
        return any(topic_lower in msg.lower() for msg in self.content)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation."""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "started_at": self.started_at.isoformat(),
            "last_message_time": self.last_message_time.isoformat(),
            "message_count": len(self.message_ids),
            "participant_count": len(self.participant_ids),
            "participants": list(self.participant_ids),
        }
