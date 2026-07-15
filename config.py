import os
from dotenv import load_dotenv

load_dotenv()

PREFIX = os.getenv("PREFIX", ".")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

KLIPY_URL = os.getenv("KLIPY_URL")
KLIPY_KEY = os.getenv("KLIPY_KEY")