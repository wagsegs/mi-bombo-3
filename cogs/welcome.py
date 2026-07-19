import logging
import random

import discord
from discord.ext import commands

from config import (
    WELCOME_CHANNEL_ID,
    WELCOME_EMBED_COLOR,
    WELCOME_FOOTER_TEXT,
    WELCOME_GIFS,
    WELCOME_MESSAGES,
)

logger = logging.getLogger(__name__)


def build_welcome_embed(member, messages=None, gifs=None, color=None, footer_text=None):
    if not messages or not gifs:
        return None

    message = random.choice(messages)
    gif_url = random.choice(gifs)

    embed = discord.Embed(
        title="🎬 Lights. Camera. Welcome.",
        description=message.format(member=member.mention),
        color=color if color is not None else WELCOME_EMBED_COLOR,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_image(url=gif_url)
    embed.set_footer(text=footer_text or WELCOME_FOOTER_TEXT)
    return embed


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if getattr(member, "bot", False):
            return

        embed = build_welcome_embed(
            member,
            WELCOME_MESSAGES,
            WELCOME_GIFS,
            WELCOME_EMBED_COLOR,
            WELCOME_FOOTER_TEXT,
        )

        if not embed:
            logger.warning("Welcome embed skipped because the welcome lists are empty.")
            return

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

        if channel is None:
            logger.warning("Welcome channel %s was not found.", WELCOME_CHANNEL_ID)
            return

        permissions = channel.permissions_for(member.guild.me)

        if not permissions.send_messages or not permissions.embed_links:
            logger.warning("Missing permissions to send welcome embed in channel %s.", WELCOME_CHANNEL_ID)
            return

        try:
            allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
            await channel.send(
                content=member.mention,
                embed=embed,
                allowed_mentions=allowed_mentions
            )
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument) as exc:
            logger.exception("Failed to send welcome embed: %s", exc)


async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
