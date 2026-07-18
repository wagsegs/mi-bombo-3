import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.director_notes import DirectorNotesCog


def test_director_notes_embed_uses_configured_values():
    cog = DirectorNotesCog(bot=None)
    embed = cog._build_embed(ctx=None)

    assert embed.title == "🎬 DIRECTOR'S NOTES"
    assert "QUIET ON SET!" in embed.description
    assert embed.footer.text == "MI BOMBO Studios"
    assert embed.color.value == 0x7B61FF
