import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

import database
import progression
import scheduler
from ai import gemini
from config import (
    MANUAL_STUDIO_MODE,
    STUDIO_PREFIX,
    NEWSPAPER_CHANNEL_ID,
    WEEKLY_CAST_CHANNEL_ID,
    LORE_MIN_PARTICIPANTS,
    LORE_MIN_MESSAGES,
    LORE_MAX_AVERAGE_REPLY_GAP_SECONDS,
    LORE_MIN_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)


class StudioManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_owner(self, ctx: commands.Context) -> bool:
        if not ctx.guild or ctx.author.id != ctx.guild.owner_id:
            await ctx.send("🎬 The Director's Console is for the Studio Director only.")
            return False
        return True

    @commands.command(name="bomboclathelp")
    async def bomboclathelp(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎬 Studio Command Deck",
            description="Manual Studio controls for MI BOMBO.",
            color=discord.Color(0x7B61FF),
        )
        embed.add_field(
            name="🎬 Studio",
            value="• $news — Generate today's newspaper preview\n• $publishnews — Publish the stored newspaper\n• $weeklycast — Generate this week's cast preview\n• $publishcast — Publish the stored weekly cast",
            inline=False,
        )
        embed.add_field(
            name="📖 Lore",
            value="• $lorestart — Begin lore recording\n• $lorestop — End lore recording\n• $testlore — Generate a lore test preview",
            inline=False,
        )
        embed.add_field(
            name="🎭 Progression",
            value="• .screentime — View your current production status\n• .leaderboard — View the studio leaderboard\n• .profile — View an actor profile",
            inline=False,
        )
        embed.add_field(
            name="🛠️ Admin",
            value="• $promote — Promote a member to a role\n• $demote — Remove progression roles\n• $resetscreentime — Reset a user's screen time\n• $reloadscheduler — Reload the scheduler\n• $testnewspaper — Generate a newspaper preview\n• $testcast — Generate a cast preview",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="news")
    async def news(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        if MANUAL_STUDIO_MODE:
            await self._generate_and_preview_newspaper(ctx)
            return
        await ctx.send("Automatic Studio publishing is currently disabled in manual mode.")

    @commands.command(name="publishnews")
    async def publishnews(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        content = await database.get_latest_studio_content("newspaper")
        if not content:
            await ctx.send("No generated newspaper is stored yet.")
            return
        channel = self.bot.get_channel(NEWSPAPER_CHANNEL_ID)
        if not channel:
            await ctx.send("The newspaper channel is not available.")
            return
        payload = json.loads(content["payload"])
        embed = self._build_newspaper_embed(payload)
        await channel.send(embed=embed)
        await database.mark_studio_content_published("newspaper")
        await ctx.send("The newspaper has been published to the studio bulletin.")

    @commands.command(name="weeklycast")
    async def weeklycast(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        if MANUAL_STUDIO_MODE:
            await self._generate_and_preview_weekly_cast(ctx)
            return
        await ctx.send("Automatic Studio publishing is currently disabled in manual mode.")

    @commands.command(name="publishcast")
    async def publishcast(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        content = await database.get_latest_studio_content("weekly_cast")
        if not content:
            await ctx.send("No generated weekly cast is stored yet.")
            return
        channel = self.bot.get_channel(WEEKLY_CAST_CHANNEL_ID)
        if not channel:
            await ctx.send("The weekly cast channel is not available.")
            return
        payload = json.loads(content["payload"])
        embed = self._build_weekly_cast_embed(payload)
        await channel.send(embed=embed)
        await database.mark_studio_content_published("weekly_cast")
        await ctx.send("The weekly cast has been published to the studio bulletin.")

    @commands.command(name="lorestart")
    async def lorestart(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        started = await database.start_lore_session(ctx.guild.id, ctx.channel.id, ctx.author.id)
        if not started:
            await ctx.send("A lore recording session is already active.")
            return
        await ctx.send("🎬 Lore recording is now live. Future eligible conversations will be considered for studio lore.")

    @commands.command(name="lorestop")
    async def lorestop(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        stopped = await database.stop_lore_session(ctx.guild.id)
        if not stopped:
            await ctx.send("No active lore recording session was found.")
            return
        await ctx.send("📖 Lore recording has ended.")

    @commands.command(name="testlore")
    async def testlore(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        await ctx.send("Lore generation is available through the manual Studio workflow once eligible conversations are collected.")

    @commands.command(name="reloadscheduler")
    async def reloadscheduler(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        scheduler.initialize(self.bot)
        await scheduler.start()
        await ctx.send("Scheduler reloaded.")

    @commands.command(name="promote")
    async def promote(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not await self._ensure_owner(ctx):
            return
        current_user = await database.get_user(member.id)
        current_role_id = current_user.get('current_role_id') if current_user else None
        for progression_role_id in progression.PROGRESSION_ROLES:
            progression_role = ctx.guild.get_role(progression_role_id)
            if progression_role and progression_role in member.roles:
                await member.remove_roles(progression_role, reason="Studio admin promotion")
        await member.add_roles(role, reason="Studio admin promotion")
        await database.set_user_role(member.id, role.id)
        await database.promote_user(member.id, current_role_id, role.id)
        await ctx.send(f"{member.mention} has been promoted to {role.mention}.")

    @commands.command(name="demote")
    async def demote(self, ctx: commands.Context, member: discord.Member):
        if not await self._ensure_owner(ctx):
            return
        for role_id in progression.PROGRESSION_ROLES:
            role = ctx.guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Studio admin demotion")
        await database.set_user_role(member.id, None)
        await ctx.send(f"{member.mention} has been demoted from progression roles.")

    @commands.command(name="resetscreentime")
    async def resetscreentime(self, ctx: commands.Context, member: discord.Member):
        if not await self._ensure_owner(ctx):
            return
        await database.reset_user_screen_time(member.id)
        await ctx.send(f"{member.mention}'s screen time has been reset.")

    @commands.command(name="testnewspaper")
    async def testnewspaper(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        await self._generate_and_preview_newspaper(ctx)

    @commands.command(name="testcast")
    async def testcast(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        await self._generate_and_preview_weekly_cast(ctx)

    async def _generate_and_preview_newspaper(self, ctx: commands.Context):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        messages = await database.get_messages_between(start_time, end_time)
        if not messages:
            await ctx.send("No recent messages were found for a newspaper preview.")
            return
        newspaper_json = await gemini.generate_newspaper_data(messages)
        if not newspaper_json:
            await ctx.send("The studio could not generate a newspaper preview right now.")
            return
        try:
            data = json.loads(newspaper_json)
        except json.JSONDecodeError:
            await ctx.send("The studio received an invalid newspaper draft.")
            return
        await database.save_studio_content("newspaper", json.dumps(data))
        embed = self._build_newspaper_embed(data)
        await ctx.send(embed=embed)

    async def _generate_and_preview_weekly_cast(self, ctx: commands.Context):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        messages = await database.get_messages_between(start_time, end_time)
        if not messages:
            await ctx.send("No recent messages were found for a weekly cast preview.")
            return
        cast_json = await gemini.generate_weekly_cast_data(messages)
        if not cast_json:
            await ctx.send("The studio could not generate a weekly cast preview right now.")
            return
        try:
            data = json.loads(cast_json)
        except json.JSONDecodeError:
            await ctx.send("The studio received an invalid weekly cast draft.")
            return
        await database.save_studio_content("weekly_cast", json.dumps(data))
        embed = self._build_weekly_cast_embed(data)
        await ctx.send(embed=embed)

    def _build_newspaper_embed(self, data: dict) -> discord.Embed:
        embed = discord.Embed(
            title=f"📰 {data.get('headline', 'MI BOMBO Daily')}",
            description=data.get('summary', ''),
            color=discord.Color(0x7B61FF),
        )
        if data.get('funniest_moments'):
            embed.add_field(name='😂 Funniest Moments', value=data.get('funniest_moments', ''), inline=False)
        if data.get('lore_updates'):
            embed.add_field(name='📖 Lore Updates', value=data.get('lore_updates', ''), inline=False)
        if data.get('cast_candidates'):
            embed.add_field(name='⭐ Cast Candidates', value=data.get('cast_candidates', ''), inline=False)
        embed.set_footer(text='MI BOMBO Studios | Manual Preview')
        return embed

    def _build_weekly_cast_embed(self, data: dict) -> discord.Embed:
        embed = discord.Embed(
            title='🎭 Weekly Cast Preview',
            description=f"Anime Style: **{data.get('anime_style', 'Unknown')}**",
            color=discord.Color(0x7B61FF),
        )
        for member in data.get('main_cast', []):
            value = (
                f"**Position:** {member.get('position', 'Unknown')}\n"
                f"**Character:** {member.get('character_description', 'TBD')}\n"
                f"**Reason:** {member.get('reason', 'Outstanding performance')}"
            )
            embed.add_field(name=f"{member.get('nickname', 'Unknown')}", value=value, inline=False)
        embed.set_footer(text='MI BOMBO Studios | Manual Preview')
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(StudioManagementCog(bot))
