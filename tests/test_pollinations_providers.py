import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import text_provider


def test_text_provider_uses_pollinations_endpoint(monkeypatch):
    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def text(self):
            return '{"choices": [{"text": "ok"}]}'

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None):
            return FakeResponse()

    monkeypatch.setattr(text_provider.aiohttp, "ClientSession", lambda *args, **kwargs: FakeSession())
    monkeypatch.setenv("POLLINATIONS_BASE_URL", "https://example.test")

    result = asyncio.run(text_provider.generate_text("hello"))

    assert result == "ok"
