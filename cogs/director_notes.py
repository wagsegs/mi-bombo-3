import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands

from utils.output_gateway import MessageType, send_output

from config import (
    DIRECTORS_COLOR,
    DIRECTORS_DESCRIPTION,
    DIRECTORS_FOOTER,
    DIRECTORS_MEDIA,
    DIRECTORS_TITLE,
)

logger = logging.getLogger(__name__)

GUIDE_SECTIONS = [
    {
        "title": "🎬 WELCOME TO MI BOMBO STUDIOS",
        "description": (
            "Every new arrival joins the cast. Every conversation contributes to the production.\n\n"
            "Some scenes are quiet. Some are loud. All of them matter. "
            "Welcome to the set, and welcome to the story. <:catnoted:1529429237675589753>"
        ),
        "fields": [
            (
                "The atmosphere",
                "This is a studio built around conversation, presence, and shared energy."
                " The people here make the scene.",
            )
        ],
    },
    {
        "title": "🎬 STUDIO RULES",
        "description": "The Director keeps it simple: respect everyone, don't ruin the set, and keep the production moving without needless drama.",
        "fields": [
            ("Respect everyone", "Treat the cast and crew like people, not props."),
            ("Don't ruin the set", "Keep the space clean, useful, and worth showing up for."),
            ("No unnecessary drama", "If a scene is messy, leave it off camera."),
            ("Let everyone enjoy filming", "Make space for new voices, good energy, and real conversation."),
            ("Follow Discord ToS", "Keep it safe, respectful, and within the rules of the platform."),
        ],
    },
    {
        "title": "🎬 KNOW YOUR SET",
        "description": "Each channel has a role. Some are for headlines, some are for heart, and some are for the weird little moments that make the studio feel alive.",
        "fields": [
            ("#casting", "Where roles are earned and promotions are announced."),
            ("#bombo-times", "The studio's daily headlines and the chaos that follows."),
            ("#best-takes", "The memories worth replaying."),
            ("#stage-floor", "The main stage. Most of the action happens here."),
            ("#dear-basketball", "A quieter corner for personal thoughts and softer scenes."),
            ("#communal-shower", "A little messy, a little unfiltered, and very much part of the vibe."),
            ("#hidden-quests", "For the curious. If you found it, you already belong."),
            ("#private-island", "A more exclusive corner of the studio for the people who keep showing up."),
        ],
    },
    {
        "title": "🎬 HOW PROGRESSION WORKS",
        "description": (
            "Everyone starts somewhere. The studio notices people who show up, talk naturally, and help keep the conversation alive. "
            "Quality matters more than spam. Extra, Guest Star, Supporting Cast, Main Cast, Main Character, Scene Stealer, Fan Favorite, Box Office, and Hall of Fame are all earned over time."
        ),
        "fields": [
            ("How it grows", "A real conversation, a steady presence, and being part of the community all matter."),
            ("The ladder", "Promotions happen through casting. The more you contribute naturally, the farther you move up the production."),
        ],
    },
    {
        "title": "🎬 WHAT BOMBOCLAT CAN DO",
        "description": "Bomboclat is here to make the studio feel alive for members.",
        "fields": [
            ("Welcome system", "New arrivals are greeted and brought into the production."),
            ("Casting announcements", "Promotions and role updates are shared with the cast."),
            ("Progression", "The studio celebrates participation and growth over time."),
            ("Headlines", "Community moments and updates are turned into visible stories."),
            ("Future events", "More community experiences are always on the horizon."),
            ("Other user features", "The experience is designed to feel active, shared, and worth returning to."),
        ],
    },
    {
        "title": "🎬 FINAL SLATE",
        "description": (
            "The cameras are rolling. Your next scene starts now. Step in, speak up, and give the studio something worth remembering. <a:sparkles:1529443142175166585>"
        ),
    },
]


class DirectorNotesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rules")
    @commands.is_owner()
    async def rules(self, ctx):
        if await self._has_recent_directors_notes(ctx):
            try:
                reply = await send_output(
                    ctx,
                    content="Director's Notes already posted recently.",
                    message_type=MessageType.DIRECTOR_NOTES,
                    module="cogs.director_notes",
                    channel=ctx.channel,
                    reply=True,
                )
                await asyncio.sleep(3)
                await reply.delete()
            except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument):
                pass
            return

        try:
            if await self._delete_command_message(ctx):
                logger.info("Deleted .rules command message in %s", ctx.channel.id)

            media_path = Path(DIRECTORS_MEDIA)
            embeds = self._build_embeds(ctx)
            if media_path.exists():
                embeds[-1].set_image(url=f"attachment://{media_path.name}")
            else:
                logger.warning("Director's notes media file not found: %s", DIRECTORS_MEDIA)

            if media_path.exists():
                file = discord.File(media_path, filename=media_path.name)
                await send_output(
                    ctx,
                    embeds=embeds,
                    file=file,
                    message_type=MessageType.DIRECTOR_NOTES,
                    module="cogs.director_notes",
                    channel=ctx.channel,
                )
                return

            await send_output(
                ctx,
                embeds=embeds,
                message_type=MessageType.DIRECTOR_NOTES,
                module="cogs.director_notes",
                channel=ctx.channel,
            )
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument) as exc:
            logger.exception("Failed to send director's notes: %s", exc)
            try:
                await send_output(
                    ctx,
                    embeds=self._build_embeds(ctx),
                    message_type=MessageType.DIRECTOR_NOTES,
                    module="cogs.director_notes",
                    channel=ctx.channel,
                )
            except Exception as fallback_exc:
                logger.exception("Fallback director's notes send failed: %s", fallback_exc)

    async def _has_recent_directors_notes(self, ctx):
        guide_titles = {section["title"] for section in GUIDE_SECTIONS}
        try:
            history = ctx.channel.history(limit=10)
            async for message in history:
                if not (message.author.bot and message.embeds):
                    continue
                for embed in message.embeds:
                    if embed.title in guide_titles and embed.footer and embed.footer.text == DIRECTORS_FOOTER:
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
        return self._build_embeds(ctx)[0]

    def _build_embeds(self, ctx):
        embeds = []
        for section in GUIDE_SECTIONS:
            embed = discord.Embed(
                title=section["title"],
                description=section["description"],
                color=DIRECTORS_COLOR,
            )

            for name, value in section.get("fields", []):
                embed.add_field(name=name, value=value, inline=False)

            if ctx and getattr(ctx, "guild", None):
                guild = ctx.guild
                if getattr(guild, "icon", None):
                    embed.set_thumbnail(url=guild.icon.url)

            embed.set_footer(text=DIRECTORS_FOOTER)
            embeds.append(embed)

        return embeds


async def setup(bot):
    await bot.add_cog(DirectorNotesCog(bot))
