from types import SimpleNamespace

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.welcome import build_welcome_embed
from config import WELCOME_GIFS, WELCOME_MESSAGES


def test_build_welcome_embed_uses_configured_values():
    member = SimpleNamespace(mention="@TestUser")

    embed = build_welcome_embed(
        member,
        ["🎬 Welcome, {member}!"],
        ["https://example.com/welcome.gif"],
        0x123456,
        "Your first scene starts here.",
    )

    assert embed.title == "🎬 Lights. Camera. Welcome."
    assert embed.description == "🎬 Welcome, @TestUser!"
    assert embed.color.value == 0x123456
    assert embed.footer.text == "Your first scene starts here."
    assert embed.image.url == "https://example.com/welcome.gif"
    assert embed.timestamp is not None


def test_build_welcome_embed_returns_none_for_empty_lists():
    member = SimpleNamespace(mention="@TestUser")

    assert (
        build_welcome_embed(member, [], [], 0x123456, "Footer") is None
    )


def test_welcome_content_is_loaded_from_assets():
    assert WELCOME_MESSAGES
    assert WELCOME_GIFS
    assert any("{member}" in message for message in WELCOME_MESSAGES)
