import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.gif_commands import extract_custom_query


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
