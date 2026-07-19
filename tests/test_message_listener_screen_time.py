import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs import message_listener


class DummyHistory:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class DummyChannel:
    id = 1
    name = "general"

    def history(self, limit=50):
        return DummyHistory()


class DummyMessage:
    def __init__(self):
        self.id = 42
        self.author = SimpleNamespace(
            id=123,
            bot=False,
            name="TestUser",
            display_name="TestUser",
        )
        self.webhook_id = None
        self.channel = DummyChannel()
        self.content = "A thoughtful conversation message"
        self.attachments = []
        self.reference = None
        self.created_at = datetime.now(timezone.utc)
        self.guild = None


def test_on_message_awaits_screen_time_bonus_calculation(monkeypatch):
    message = DummyMessage()

    async def fake_get_or_create_user(**kwargs):
        return None

    async def fake_save_message(**kwargs):
        return None

    async def fake_update_screen_time(**kwargs):
        return 3

    async def fake_calculate_screen_time_bonuses(**kwargs):
        return 3

    async def fake_check_and_promote(*args, **kwargs):
        return None

    async def fake_create_casting_update_embed(*args, **kwargs):
        return None

    class DummyTracker:
        async def track_message(self, **kwargs):
            return None

    monkeypatch.setattr(message_listener.database, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(message_listener.database, "save_message", fake_save_message)
    monkeypatch.setattr(message_listener.database, "update_screen_time", fake_update_screen_time)
    monkeypatch.setattr(message_listener.progression, "calculate_screen_time_bonuses", fake_calculate_screen_time_bonuses)
    monkeypatch.setattr(message_listener.progression, "check_and_promote", fake_check_and_promote)
    monkeypatch.setattr(message_listener.progression, "create_casting_update_embed", fake_create_casting_update_embed)
    monkeypatch.setattr(message_listener, "get_tracker", lambda: DummyTracker())

    listener = message_listener.MessageListenerCog(bot=None)

    asyncio.run(listener.on_message(message))
