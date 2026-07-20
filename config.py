import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PREFIX = os.getenv("PREFIX", ".")
STUDIO_PREFIX = os.getenv("STUDIO_PREFIX", "$")
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

If I yell **"CUT!"**, that's the end of the scene.

### 🎥 EVERYTHING ELSE

• Do your thing.
• Keep the production rolling.
• Don't make me rewrite the script.
• Give the audience a show worth watching.

🔥 ──────────────────── 🔥

**🎬 KNOW YOUR SET**

**#casting**  
This is where promotions happen. Impress the Director and you'll work your way from **Extra** to **Main Cast**.

**#bombo-times**  
If you make today's headlines... you either cooked or completely crashed out.

**#best-takes**  
The moments worth replaying. Absolute Cinema.

**#stage-floor**  
The main set. Most of the stuff happens here.

**#dear-basketball**  
basically dear diary.

**#communal-shower**  
Keep it clean.  
...Mentally, preferably.

**#hidden-quests**  
If you found this channel, congratulations.  

**#private-island**  
VIP access.  
If you're not here, work harder.  
Or bribe the producer.

🔥 ──────────────────── 🔥

### 🎬 LIGHTS!

## 🎥 CAMERA!!

# 🗣️ **LET'S FUCKING GO!!!**
""",
)
DIRECTORS_FOOTER = os.getenv("DIRECTORS_FOOTER", "MI BOMBO Studios")
DIRECTORS_COLOR = int(os.getenv("DIRECTORS_COLOR", "0x7B61FF"), 16)
DIRECTORS_MEDIA = os.getenv("DIRECTORS_MEDIA", str(BASE_DIR / "lesgo.gif"))

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================
# AI CONFIGURATION
# ============================================================
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "pollinations")
TEXT_PROVIDER = os.getenv("TEXT_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
POLLINATIONS_BASE_URL = os.getenv("POLLINATIONS_BASE_URL")
POLLINATIONS_IMAGE_BASE_URL = os.getenv("POLLINATIONS_IMAGE_BASE_URL")
POLLINATIONS_TEXT_BASE_URL = os.getenv("POLLINATIONS_TEXT_BASE_URL")
AI_CHAT_ENABLED = os.getenv("AI_CHAT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

# ============================================================
# SERVER & CHANNELS
# ============================================================
SERVER_ID = int(os.getenv("SERVER_ID", "1526652261764173874"))
CASTING_CHANNEL_ID = int(os.getenv("CASTING_CHANNEL_ID", "1527244160917045278"))
NEWSPAPER_CHANNEL_ID = int(os.getenv("NEWSPAPER_CHANNEL_ID", "1526652930604662955"))
WEEKLY_CAST_CHANNEL_ID = int(os.getenv("WEEKLY_CAST_CHANNEL_ID", "1526652930604662955"))

# Channels to exclude from message tracking, screen time, and content generation
EXCLUDED_TRACKING_CHANNELS = {
    1527243737883738172,  # Director's Room
    1527702798655946842,  # heh
}

# ============================================================
# PROGRESSION ROLES (Mutually Exclusive)
# ============================================================
PROGRESSION_ROLES = [
    1526865658955038721,  # members
    1528480740491132948,  # Extra
    1526874639941242930,  # Guest Star
    1526874159496429568,  # Supporting Cast
    1526874354141626368,  # Main Cast
    1526874419576701058,  # Main Character
    1528481045094207679,  # Fan Favorite
    1528481466223427725,  # Scene Stealer
    1528481587619172555,  # Box Office Legend
    1526875250313396325,  # Hall of Fame
]

# Staff roles that are NEVER touched by progression
STAFF_ROLES = {
    "Producer": None,
    "Executive Producer": None,
    "Director": None,
}

# Screen Time progression balancing
SCREEN_TIME_REWARD_CONFIG = {
    "short_threshold": 10,
    "medium_threshold": 100,
    "long_threshold": 250,
    "short_reward": 0,
    "medium_reward": 1,
    "long_reward": 2,
}
SCREEN_TIME_PARTICIPANT_REWARD = 1
SCREEN_TIME_REPLY_REWARD = 1
SCREEN_TIME_DIMINISHING_RETURNS = {
    "window_seconds": 1800,
    "full_reward_messages": 3,
    "reduced_reward_messages": 8,
    "reduction_factor": 0.5,
    "minimum_reward_factor": 0.2,
}
SCREEN_TIME_CONSISTENCY_BONUS = {
    "window_days": 7,
    "threshold_days": 2,
    "bonus_per_day_bucket": 1,
    "max_bonus": 2,
}

# Screen Time thresholds for automatic promotion
SCREEN_TIME_THRESHOLDS = {
    1526865658955038721: 0,      # members
    1528480740491132948: 250,    # Extra
    1526874639941242930: 900,    # Guest Star
    1526874159496429568: 3200,  # Supporting Cast
    1526874354141626368: 11000, # Main Cast
    1526874419576701058: 32000, # Main Character
    1528481045094207679: 90000, # Fan Favorite
    1528481466223427725: 220000, # Scene Stealer
    1528481587619172555: 500000, # Box Office Legend
    1526875250313396325: 900000, # Hall of Fame
}

# ============================================================
# STUDIO CONFIGURATION
# ============================================================
MANUAL_STUDIO_MODE = True
LORE_MIN_PARTICIPANTS = 3
LORE_MIN_MESSAGES = 20
LORE_MAX_AVERAGE_REPLY_GAP_SECONDS = 60
LORE_MIN_DURATION_SECONDS = 300

# ============================================================
# SCHEDULER CONFIGURATION
# ============================================================
SCHEDULER_TIMEZONE = "Europe/Berlin"
NEWSPAPER_SCHEDULE = "09:00"  # Daily at 09:00
WEEKLY_CAST_SCHEDULE = "09:00"  # Sunday at 09:00
WEEKLY_CAST_DAY = "sun"  # Sunday