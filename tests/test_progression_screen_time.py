import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import discord

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import progression


def test_calculate_screen_time_bonuses_uses_single_length_reward(monkeypatch):
    assert asyncio.run(progression.calculate_screen_time_bonuses(120, 3)) == 3


def test_reply_bonus_is_small_and_modular(monkeypatch):
    assert asyncio.run(progression.calculate_screen_time_bonuses(20, 1, is_reply=True)) == 2


def test_casting_embed_uses_cinematic_status_instead_of_screen_time(monkeypatch):
    async def fake_get_user(user_id):
        return {"screen_time": 420}

    monkeypatch.setattr(progression.database, "get_user", fake_get_user)

    member = SimpleNamespace(
        id=123,
        mention="<@123>",
        display_avatar=SimpleNamespace(url="https://example.com/avatar.png"),
    )
    role = SimpleNamespace(name="Lead", mention="@Lead", color=discord.Color(0x7B61FF))

    embed = asyncio.run(progression.create_casting_update_embed(member, role))

    assert "Screen Time" not in [field.name for field in embed.fields]
    assert any(field.name == "Production Status" for field in embed.fields)
    assert "The Director" in embed.fields[0].value
