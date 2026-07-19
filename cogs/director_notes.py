import logging
from pathlib import Path

import discord
from discord.ext import commands

from config import (
    DIRECTORS_COLOR,
    DIRECTORS_DESCRIPTION,
    DIRECTORS_FOOTER,
    DIRECTORS_MEDIA,
    DIRECTORS_TITLE,
)

logger = logging.getLogger(__name__)


class DirectorNotesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rules")
    @commands.has_permissions(administrator=True)
    async def rules(self, ctx):
        if await self._has_recent_directors_notes(ctx):
            try:
                reply = await ctx.reply("Director's Notes already posted recently.")
                await asyncio.sleep(3)
                await reply.delete()
            except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument):
                pass
            return

        try:
            if await self._delete_command_message(ctx):
                logger.info("Deleted .rules command message in %s", ctx.channel.id)

            media_path = Path(DIRECTORS_MEDIA)
            if not media_path.exists():
                logger.warning("Director's notes media file not found: %s", DIRECTORS_MEDIA)
                await ctx.send(embed=self._build_embed(ctx))
                return

            file = discord.File(media_path, filename=media_path.name)
            await ctx.send(embed=self._build_embed(ctx), file=file)
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument) as exc:
            logger.exception("Failed to send director's notes: %s", exc)
            try:
                await ctx.send(embed=self._build_embed(ctx))
            except Exception as fallback_exc:
                logger.exception("Fallback director's notes send failed: %s", fallback_exc)

    async def _has_recent_directors_notes(self, ctx):
        try:
            history = ctx.channel.history(limit=10)
            async for message in history:
                if message.author.bot and message.embeds:
                    for embed in message.embeds:
                        if embed.title == DIRECTORS_TITLE:
                            return True
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument):
            return False

        return False

    async def _delete_command_message(self, ctx):
        try:
            permissions = ctx.channel.permissions_for(ctx.guild.me)
            if not permissions.manage_messages:
                return False

            await ctx.message.delete()
            return True
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument):
            return False

    def _build_embed(self, ctx):
        embed = discord.Embed(
            title=DIRECTORS_TITLE,
            description=DIRECTORS_DESCRIPTION,
            color=DIRECTORS_COLOR,
        )

        # ADD THIS
        media_path = Path(DIRECTORS_MEDIA)
        embed.set_image(url=f"attachment://{media_path.name}")

        embed.set_footer(text=DIRECTORS_FOOTER)
        return embed


async def setup(bot):
    await bot.add_cog(DirectorNotesCog(bot))
