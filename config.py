import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PREFIX = os.getenv("PREFIX", ".")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

KLIPY_URL = os.getenv("KLIPY_URL")
KLIPY_KEY = os.getenv("KLIPY_KEY")

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "1526652261764173877"))
WELCOME_EMBED_COLOR = int(os.getenv("WELCOME_EMBED_COLOR", "0x7B61FF"), 16)
WELCOME_FOOTER_TEXT = os.getenv(
    "WELCOME_FOOTER_TEXT",
    "Your first scene starts when you send your first message.",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


def _load_asset_lines(filename):
    path = ASSETS_DIR / filename

    if not path.exists():
        return []

    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


WELCOME_MESSAGES = _load_asset_lines("welcome_messages.txt") or [
    "🎬 Lights. Camera. Welcome, {member}.",
]
WELCOME_GIFS = _load_asset_lines("welcome_gifs.txt") or [
    "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
]

DIRECTORS_TITLE = os.getenv("DIRECTORS_TITLE", "🎬 DIRECTOR'S NOTES")
DIRECTORS_DESCRIPTION = os.getenv(
    "DIRECTORS_DESCRIPTION",
    "QUIET ON SET!\n\nAlright, listen up.\n\nYou're here because you're part of the cast now.\n\nStay in character.\nRespect the people you're filming with.\nDon't trash the set.\nDon't make the crew clean up your mess.\n\nIf the Director yells \"CUT!\"\n...that's the end of the scene.\n\nEverything else?\n\nDo your thing.\nKeep the production rolling.\nDon't make me rewrite the script.\nGive the audience a show worth watching.\n\n...\n\nAlright.\n\nLIGHTS!\n\nCAMERA!!\n\nLET'S FUCKING GO!!!",
)
DIRECTORS_FOOTER = os.getenv("DIRECTORS_FOOTER", "MI BOMBO Studios")
DIRECTORS_COLOR = int(os.getenv("DIRECTORS_COLOR", "0x7B61FF"), 16)
DIRECTORS_MEDIA = os.getenv("DIRECTORS_MEDIA", str(BASE_DIR / "lesgo.gif"))