import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.gif_commands import extract_custom_query, build_custom_gif_details


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (".c door shutting", "door shutting"),
        (".c cat laughing", "cat laughing"),
        (".c", None),
        (".c   ", None),
    ],
)
def test_extract_custom_query(content, expected):
    assert extract_custom_query(content, ".") == expected


def test_build_custom_gif_details_strips_mentions_from_query():
    ctx = SimpleNamespace(
        author=SimpleNamespace(mention="@User"),
        message=SimpleNamespace(
            content=".c calculus <@1320436656263921782>",
            mentions=[SimpleNamespace(mention="<@1320436656263921782>")],
        ),
    )

    query, description = build_custom_gif_details(ctx, ".")

    assert query == "calculus"
    assert description == '@User "calculus" <@1320436656263921782>'
