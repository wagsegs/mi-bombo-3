import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

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
        return None


class FakeMessage:
    def __init__(self):
        self.edits = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)
        return self


def test_newspaper_generation_updates_the_same_progress_message(monkeypatch):
    cog = studio_management.StudioManagementCog(SimpleNamespace(get_channel=lambda _id: None))
    ctx = DummyContext(author_id=1, owner_id=1)
    progress_message = FakeMessage()

    async def fake_send_output(destination, **kwargs):
        if kwargs.get("embed") is not None:
            return progress_message
        return None

    async def fake_get_eligible_conversations(*args, **kwargs):
        return [
            {
                "id": 1,
                "channel_name": "general",
                "started_at": None,
                "ended_at": None,
                "message_ids": [1],
                "participant_ids": [1],
                "messages": [
                    {"username": "Alice", "content": "hello", "created_at": None, "user_id": 1}
                ],
            }
        ]

    async def fake_summarize_conversations(*args, **kwargs):
        return [
            {
                "conversation_id": 1,
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
        ]

    async def fake_generate_final_newspaper_json(*args, **kwargs):
        return json.dumps({"headline": "Daily", "summary": "ok", "funniest_moments": "", "lore_updates": "", "cast_candidates": ""})

    async def fake_save_studio_content(*args, **kwargs):
        return None

    monkeypatch.setattr(studio_management, "send_output", fake_send_output)
    monkeypatch.setattr(studio_management.studio_editor_pipeline, "get_eligible_conversations", fake_get_eligible_conversations)
    monkeypatch.setattr(studio_management.studio_editor_pipeline, "summarize_conversations", fake_summarize_conversations)
    monkeypatch.setattr(studio_management.studio_editor_pipeline, "generate_final_newspaper_json", fake_generate_final_newspaper_json)
    monkeypatch.setattr(studio_management.database, "save_studio_content", fake_save_studio_content)

    asyncio.run(cog._generate_and_preview_newspaper(ctx))

    assert len(progress_message.edits) >= 2
    final_embed = progress_message.edits[-1]["embed"]
    assert final_embed.title.startswith("📰")
