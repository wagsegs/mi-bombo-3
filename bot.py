import asyncio
import logging

import discord
from discord.ext import commands

from config import PREFIX, DISCORD_TOKEN

COGS = [
    "cogs.gif_commands"
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
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

    print("🤖 MI BOM3O is online!")


async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")

    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())