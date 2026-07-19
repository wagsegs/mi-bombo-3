import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tracking import ConversationTracker


def test_conversation_tracker_normalizes_timestamps_to_utc():
    tracker = ConversationTracker()

    conversation = asyncio.run(
        tracker.track_message(
            message_id=1,
            user_id=101,
            content="hello",
            channel_id=999,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )
    )

    assert conversation is not None
    assert conversation.started_at.tzinfo is not None
    assert conversation.started_at.utcoffset() == timezone.utc.utcoffset(conversation.started_at)
    assert conversation.last_message_time.tzinfo is not None
