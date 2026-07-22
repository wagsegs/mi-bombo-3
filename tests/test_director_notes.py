import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.director_notes import DirectorNotesCog


def test_director_notes_builds_a_cinematic_guide_series():
    cog = DirectorNotesCog(bot=None)
    embeds = cog._build_embeds(ctx=None)

    assert len(embeds) == 6
    assert embeds[0].title == "🎬 WELCOME TO MI BOMBO STUDIOS"
    assert "cast" in embeds[0].description.lower()
    assert embeds[1].title == "🎬 STUDIO RULES"
    assert "respect everyone" in embeds[1].description.lower()
    assert embeds[3].title == "🎬 HOW PROGRESSION WORKS"
    assert "extra" in embeds[3].description.lower()
    assert embeds[-1].footer.text == "MI BOMBO Studios"
    assert embeds[-1].color.value == 0x7B61FF
