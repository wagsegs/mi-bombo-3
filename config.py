import os
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
WELCOME_MESSAGES = [
    "🎬 Lights. Camera. Welcome, {member}.",
    "🎭 The cast just got a little bigger.",
    "🎞️ The studio is ready for your first scene.",
    "✨ A new actor has stepped onto the set.",
]
WELCOME_GIFS = [
    "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
]