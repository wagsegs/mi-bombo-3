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

    async def fake_get_messages_between(*args, **kwargs):
        return [{"username": "Alice", "content": "hello", "created_at": None, "user_id": 1}]

    async def fake_generate_newspaper_data(*args, **kwargs):
        return json.dumps({"headline": "Daily", "summary": "ok", "funniest_moments": "", "lore_updates": "", "cast_candidates": ""})

    async def fake_save_studio_content(*args, **kwargs):
        return None

    monkeypatch.setattr(studio_management, "send_output", fake_send_output)
    monkeypatch.setattr(studio_management.database, "get_messages_between", fake_get_messages_between)
    monkeypatch.setattr(studio_management.text_provider, "generate_newspaper_data", fake_generate_newspaper_data)
    monkeypatch.setattr(studio_management.database, "save_studio_content", fake_save_studio_content)

    asyncio.run(cog._generate_and_preview_newspaper(ctx))

    assert len(progress_message.edits) >= 2
    final_embed = progress_message.edits[-1]["embed"]
    assert final_embed.title.startswith("📰")
