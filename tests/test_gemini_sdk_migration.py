import asyncio
import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_generate_text_uses_google_genai_client(monkeypatch):
    calls = {}

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.calls = []
            self.models = self

        def generate_content(self, *, model, contents, config):
            self.calls.append((model, contents, config))
            return types.SimpleNamespace(text="generated")

    fake_client = FakeClient("test-key")

    class FakeDeprecatedGenAI(types.ModuleType):
        def configure(self, api_key):
            raise AssertionError("deprecated google.generativeai SDK should not be used")

        def GenerativeModel(self, *args, **kwargs):
            raise AssertionError("deprecated google.generativeai SDK should not be used")

    fake_old_module = FakeDeprecatedGenAI("google.generativeai")
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_old_module)

    google_module = types.ModuleType("google")
    google_module.__path__ = []

    genai_module = types.ModuleType("google.genai")
    genai_module.Client = lambda api_key=None: fake_client
    google_module.genai = genai_module

    types_module = types.ModuleType("google.genai.types")
    types_module.GenerateContentConfig = lambda **kwargs: kwargs

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)

    sys.modules.pop("ai.gemini", None)
    gemini = importlib.import_module("ai.gemini")

    gemini.initialize("test-key")
    result = asyncio.run(gemini.generate_text("hello", system_instruction="be brief"))

    assert result == "generated"
    assert fake_client.api_key == "test-key"
    assert fake_client.calls[0][0] == "gemini-2.0-flash"
    assert fake_client.calls[0][1] == "hello"
    assert fake_client.calls[0][2]["system_instruction"] == "be brief"
