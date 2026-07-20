import asyncio
import logging

import discord
from discord.ext import commands

from config import PREFIX, STUDIO_PREFIX, DISCORD_TOKEN, DATABASE_URL

import database
import scheduler

COGS = [
    "cogs.gif_commands",
    "cogs.welcome",
    "cogs.director_notes",
    "cogs.message_listener",
    "cogs.studio_management",
    "progression",
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX, STUDIO_PREFIX),
    intents=intents,
    help_command=None,
)


@bot.event
async def on_ready():
    
    if bot.user:
        logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logging.info(f"✓ Loaded {cog}")
        except Exception as e:
            logging.error(f"✗ Failed to load {cog}: {e}")

    # Start scheduler
    try:
        scheduler.initialize(bot)
        await scheduler.start()
    except Exception as e:
        logging.error(f"✗ Failed to start scheduler: {e}")

    print("🤖 MI BOM3O is online!")


async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")

    if not DATABASE_URL:
        raise RuntimeError("Missing DATABASE_URL in .env")

    # Initialize systems
    try:
        await database.connect(DATABASE_URL)
        logging.info("✓ Database initialized")
    except Exception as e:
        logging.error(f"✗ Failed to initialize database: {e}")
        return

    try:
        async with bot:
            await bot.start(DISCORD_TOKEN)
    finally:
        try:
            await scheduler.stop()
        except Exception as e:
            logging.error(f"Error stopping scheduler: {e}")
        try:
            await database.disconnect()
        except Exception as e:
            logging.error(f"Error disconnecting from database: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())