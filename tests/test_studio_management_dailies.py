import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs import studio_management


class DummyContext:
    def __init__(self, author_id=1, owner_id=1):
        self.author = SimpleNamespace(id=author_id)
        self.guild = SimpleNamespace(owner_id=owner_id)
        self.channel = self
        self.sent = []

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))


class DummyBot:
    def get_channel(self, channel_id):
        return None


def test_dailies_lists_recent_conversations(monkeypatch):
    cog = studio_management.StudioManagementCog(DummyBot())
    ctx = DummyContext(author_id=1, owner_id=1)

    async def fake_get_recent_conversation_summaries(*args, **kwargs):
        return [
            {
                "id": 1,
                "channel_name": "general",
                "started_at": datetime(2026, 7, 20, 20, 12, 0, tzinfo=timezone.utc),
                "ended_at": datetime(2026, 7, 20, 20, 20, 14, tzinfo=timezone.utc),
                "duration_seconds": 494,
                "participant_count": 4,
                "message_count": 21,
                "is_eligible": True,
                "reasons": [],
            }
        ]

    monkeypatch.setattr(studio_management.database, "get_recent_conversation_summaries", fake_get_recent_conversation_summaries)

    asyncio.run(cog.dailies.callback(cog, ctx))

    assert len(ctx.sent) == 1
    embed = ctx.sent[0][1].get("embed")
    assert embed is not None
    assert embed.title == "🎬 Director's Dailies"
    assert any("general" in field.value for field in embed.fields)


def test_dailies_detail_preview_for_specific_conversation(monkeypatch):
    cog = studio_management.StudioManagementCog(DummyBot())
    ctx = DummyContext(author_id=1, owner_id=1)

    async def fake_get_conversation_detail(*args, **kwargs):
        return {
            "id": 3,
            "channel_name": "general",
            "started_at": datetime(2026, 7, 20, 20, 12, 0, tzinfo=timezone.utc),
            "ended_at": datetime(2026, 7, 20, 20, 19, 0, tzinfo=timezone.utc),
            "duration_seconds": 420,
            "participants": ["Alice", "Bob", "Carl"],
            "message_count": 24,
            "is_eligible": True,
            "reasons": [],
            "messages": [
                {"username": "Alice", "content": "bro who deleted the train"},
                {"username": "Bob", "content": "LMAOOO"},
                {"username": "Carl", "content": "it wasn't me"},
            ],
        }

    monkeypatch.setattr(studio_management.database, "get_conversation_detail", fake_get_conversation_detail)

    asyncio.run(cog.dailies.callback(cog, ctx, "3"))

    assert len(ctx.sent) == 1
    embed = ctx.sent[0][1].get("embed")
    assert embed is not None
    assert "Alice" in embed.fields[-1].value
    assert "bro who deleted the train" in embed.fields[-1].value


def test_publishnews_uses_output_gateway(monkeypatch):
    class FakeChannel:
        def __init__(self):
            self.sent = []

        async def send(self, *args, **kwargs):
            self.sent.append((args, kwargs))
            return None

    channel = FakeChannel()
    bot = DummyBot()
    bot.get_channel = lambda channel_id: channel
    cog = studio_management.StudioManagementCog(bot)
    ctx = DummyContext(author_id=1, owner_id=1)

    async def fake_get_latest_studio_content(*args, **kwargs):
        return {"payload": json.dumps({"headline": "Studio Update"})}

    async def fake_mark_studio_content_published(*args, **kwargs):
        return None

    calls = []

    async def fake_send_output(destination, **kwargs):
        calls.append((destination, kwargs))
        return None

    monkeypatch.setattr(studio_management.database, "get_latest_studio_content", fake_get_latest_studio_content)
    monkeypatch.setattr(studio_management.database, "mark_studio_content_published", fake_mark_studio_content_published)
    monkeypatch.setattr(studio_management, "send_output", fake_send_output)

    asyncio.run(cog.publishnews.callback(cog, ctx))

    assert any(
        destination is channel and kwargs.get("message_type") == studio_management.MessageType.NEWSPAPER
        for destination, kwargs in calls
    )
