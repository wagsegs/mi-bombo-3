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
    """
# 🎬 QUIET ON SET!

Alright, listen up.

You're here because you're part of the cast now.

### 🎭 STAY IN CHARACTER

• Respect the people you're filming with.
• Don't trash the set.
• Don't make the crew clean up your mess.

> **Director:** If I yell **"CUT!"**, that's the end of the scene.

### 🎥 EVERYTHING ELSE

• Do your thing.
• Keep the production rolling.
• Don't make me rewrite the script.
• Give the audience a show worth watching.

━━━━━━━━━━━━━━━━━━

# 🎬 LIGHTS!

# 🎥 CAMERA!!

# 🗣️ **LET'S FUCKING GO!!!**
""",
)
DIRECTORS_FOOTER = os.getenv("DIRECTORS_FOOTER", "MI BOMBO Studios")
DIRECTORS_COLOR = int(os.getenv("DIRECTORS_COLOR", "0x7B61FF"), 16)
DIRECTORS_MEDIA = os.getenv("DIRECTORS_MEDIA", str(BASE_DIR / "lesgo.gif"))