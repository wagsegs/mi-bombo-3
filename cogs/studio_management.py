import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

import database
import progression
import scheduler
from ai import image_provider, text_provider
from config import (
    STUDIO_PREFIX,
    NEWSPAPER_CHANNEL_ID,
    WEEKLY_CAST_CHANNEL_ID,
    LORE_MIN_PARTICIPANTS,
    LORE_MIN_MESSAGES,
    LORE_MAX_AVERAGE_REPLY_GAP_SECONDS,
    LORE_MIN_DURATION_SECONDS,
)
import tracking
from utils import studio_editor_pipeline
from utils.output_gateway import MessageType, send_output
from utils.timezone import utc_now

logger = logging.getLogger(__name__)


class StudioGenerationTask:
    def __init__(self, ctx: commands.Context, *, title: str, description: str, stages: list[str], footer: Optional[str] = None):
        self.ctx = ctx
        self.title = title
        self.description = description
        self.stages = list(stages)
        self.footer = footer or "MI BOMBO Studios"
        self.message = None
        self.current_stage_index = 0

    async def start(self):
        self.message = await send_output(
            self.ctx,
            embed=self._build_embed(),
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=self.ctx.channel,
        )
        return self.message

    async def update_stage(self, stage_name: str):
        if self.message is None:
            await self.start()
        if stage_name in self.stages:
            self.current_stage_index = self.stages.index(stage_name)
        else:
            self.stages.append(stage_name)
            self.current_stage_index = len(self.stages) - 1
        return await self._refresh()

    async def complete(self, embed: discord.Embed):
        if self.message is None:
            return None
        if hasattr(self.message, "edit"):
            return await self.message.edit(embed=embed)
        return None

    async def fail(self, error: str):
        embed = discord.Embed(
            title="❌ Production Failed",
            description="The Editorial Team was unable to finish today's edition.",
            color=discord.Color(0xED4245),
        )
        embed.add_field(name="Reason", value=error or "Unknown error", inline=False)
        embed.add_field(name="Status", value="Nothing has been published.", inline=False)
        embed.set_footer(text=self.footer)
        return await self.complete(embed)

    async def _refresh(self):
        if self.message is None:
            return None
        if hasattr(self.message, "edit"):
            return await self.message.edit(embed=self._build_embed())
        return None

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=discord.Color(0x7B61FF),
        )
        embed.add_field(name="⏳ Status", value="The production pipeline is actively running.", inline=False)
        for index, stage in enumerate(self.stages):
            prefix = "✅" if index < self.current_stage_index else "🔄" if index == self.current_stage_index else "⏳"
            embed.add_field(name=f"{prefix} {stage}", value="\u200b", inline=False)
        embed.set_footer(text=self.footer)
        return embed


class StudioManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_owner(self, ctx: commands.Context) -> bool:
        if not ctx.guild or ctx.author.id != ctx.guild.owner_id:
            await send_output(
                ctx,
                content="🎬 The Director's Console is for the Studio Director only.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
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
            value="• $lorestart — Begin lore recording\n• $lorestop — End lore recording\n• $testlore — Generate a lore test preview\n• $dailies — Review recent tracked conversations",
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
        await send_output(
            ctx,
            embed=embed,
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    @commands.command(name="news")
    async def news(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        await self._generate_and_preview_newspaper(ctx)

    @commands.command(name="publishnews")
    async def publishnews(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        content = await database.get_latest_studio_content("newspaper")
        if not content:
            await send_output(
                ctx,
                content="No generated newspaper is stored yet.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
            return
        channel = self.bot.get_channel(NEWSPAPER_CHANNEL_ID)
        if not channel:
            await send_output(
                ctx,
                content="The newspaper channel is not available.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
            return
        
        payload = json.loads(content["payload"])
        image_path = None
        try:
            image_prompt = payload.get("image_prompt")
            if image_prompt:
                image_path = await image_provider.generate_image(image_prompt)
            
            embed = self._build_newspaper_embed(payload, image_path)
            await send_output(
                channel,
                embed=embed,
                message_type=MessageType.NEWSPAPER,
                module="cogs.studio_management",
                channel=channel,
            )
            await database.mark_studio_content_published("newspaper")
            await send_output(
                ctx,
                content="The newspaper has been published to the studio bulletin.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
        finally:
            if image_path:
                image_provider.cleanup_temp_file(image_path)

    @commands.command(name="weeklycast")
    async def weeklycast(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        await self._generate_and_preview_weekly_cast(ctx)

    @commands.command(name="publishcast")
    async def publishcast(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        content = await database.get_latest_studio_content("weekly_cast")
        if not content:
            await send_output(
                ctx,
                content="No generated weekly cast is stored yet.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
            return
        channel = self.bot.get_channel(WEEKLY_CAST_CHANNEL_ID)
        if not channel:
            await send_output(
                ctx,
                content="The weekly cast channel is not available.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
            return
        
        payload = json.loads(content["payload"])
        image_path = None
        try:
            anime_prompt = payload.get("anime_prompt")
            if anime_prompt:
                image_path = await image_provider.generate_image(anime_prompt)
            
            embed = self._build_weekly_cast_embed(payload, image_path)
            await send_output(
                channel,
                embed=embed,
                message_type=MessageType.WEEKLY_CAST,
                module="cogs.studio_management",
                channel=channel,
            )
            await database.mark_studio_content_published("weekly_cast")
            await send_output(
                ctx,
                content="The weekly cast has been published to the studio bulletin.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
        finally:
            if image_path:
                image_provider.cleanup_temp_file(image_path)

    @commands.command(name="lorestart")
    async def lorestart(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        started = await database.start_lore_session(ctx.guild.id, ctx.channel.id, ctx.author.id)
        if not started:
            await send_output(
            ctx,
            content="A lore recording session is already active.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )
            return
        await send_output(
            ctx,
            content="🎬 Lore recording is now live. Future eligible conversations will be considered for studio lore.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    @commands.command(name="lorestop")
    async def lorestop(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        stopped = await database.stop_lore_session(ctx.guild.id)
        if not stopped:
            await send_output(
            ctx,
            content="No active lore recording session was found.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )
            return
        await send_output(
            ctx,
            content="📖 Lore recording has ended.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    @commands.command(name="testlore")
    async def testlore(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        
        progress_task = StudioGenerationTask(
            ctx,
            title="🎬 MI BOMBO Studios",
            description="The Editorial Team is writing a new lore episode...",
            stages=[
                "Initializing production...",
                "Collecting eligible conversations...",
                "Writing lore episode...",
                "Generating artwork...",
                "Finalizing episode...",
            ],
            footer="MI BOMBO Studios | Lore Preview",
        )
        await progress_task.start()
        try:
            await progress_task.update_stage("Collecting eligible conversations...")
            recent_conversations = await database.get_recent_conversation_summaries(limit=10)
            if not recent_conversations:
                await progress_task.fail("No eligible conversations found for lore generation.")
                return
            
            eligible_messages = []
            for conv in recent_conversations:
                started_at = conv.get('started_at')
                ended_at = conv.get('ended_at')
                if started_at and ended_at:
                    messages = await database.get_messages_between(started_at, ended_at)
                    if messages:
                        eligible_messages.extend(messages)
            
            if not eligible_messages:
                await progress_task.fail("No messages found in eligible conversations.")
                return

            await progress_task.update_stage("Writing lore episode...")
            lore_json = await text_provider.generate_lore_update([
                {
                    'username': msg.get('username', 'Unknown'),
                    'content': msg.get('content', ''),
                    'created_at': msg.get('created_at'),
                    'user_id': msg.get('user_id'),
                }
                for msg in eligible_messages[:100]
                if msg.get('content')
            ])
            
            if not lore_json:
                await progress_task.fail("The studio could not generate a lore episode right now.")
                return
            
            try:
                data = json.loads(lore_json)
            except json.JSONDecodeError:
                await progress_task.fail("The studio received an invalid lore draft.")
                return

            await progress_task.update_stage("Generating artwork...")
            image_prompt = data.get("image_prompt")
            if image_prompt:
                image_path = await image_provider.generate_image(image_prompt)
                data["image_path"] = image_path
            
            embed = self._build_lore_embed(data, image_path)

            await progress_task.update_stage("Finalizing episode...")
            await progress_task.complete(embed)
        except Exception as exc:
            logger.exception("Failed to generate lore preview")
            await progress_task.fail(str(exc) or "Unexpected error")

    def _build_lore_embed(self, data: dict, image_path: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"📖 {data.get('title', 'Lore Episode')}",
            description=data.get('summary', ''),
            color=discord.Color(0x7B61FF),
        )
        if data.get('lore'):
            embed.add_field(name='🎭 Episode Lore', value=data.get('lore', ''), inline=False)
        embed.set_footer(text='MI BOMBO Studios | Lore Preview')
        if image_path:
            embed.set_image(file=discord.File(image_path))
        return embed

    @commands.command(name="dailies")
    async def dailies(self, ctx: commands.Context, conversation_number: Optional[str] = None):
        if not await self._ensure_owner(ctx):
            return

        if conversation_number:
            try:
                conv_id = int(conversation_number)
            except ValueError:
                await send_output(
                    ctx,
                    content="Please provide a valid conversation number.",
                    message_type=MessageType.COMMAND_RESPONSE,
                    module="cogs.studio_management",
                    channel=ctx.channel,
                )
                return
            detail = await database.get_conversation_detail(conv_id)
            if not detail:
                await send_output(
                    ctx,
                    content=f"No conversation found with the number {conv_id}.",
                    message_type=MessageType.COMMAND_RESPONSE,
                    module="cogs.studio_management",
                    channel=ctx.channel,
                )
                return
            await self._send_conversation_detail_embed(ctx, detail)
            return

        summaries = await database.get_recent_conversation_summaries(limit=5)
        embed = discord.Embed(
            title="🎬 Director's Dailies",
            description="Recent tracked conversations from the studio archive.",
            color=discord.Color(0x7B61FF),
        )
        if not summaries:
            embed.add_field(name="No Dailies Recorded", value="No tracked conversations have been recorded yet.", inline=False)
            await send_output(
                ctx,
                embed=embed,
                message_type=MessageType.COMMAND_RESPONSE,
                module="cogs.studio_management",
                channel=ctx.channel,
            )
            return

        for row in summaries:
            started_at = row.get('started_at')
            ended_at = row.get('ended_at')
            duration_seconds = 0
            if started_at and ended_at:
                duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
            message_count = len(row.get('message_ids') or [])
            participant_count = len(row.get('participant_ids') or [])
            average_gap_seconds = 0.0
            messages = []
            if row.get('message_ids'):
                try:
                    message_rows = await database.get_messages_between(started_at, ended_at or started_at)
                    if message_rows:
                        message_rows = [msg for msg in message_rows if msg.get('message_id') in (row.get('message_ids') or [])]
                        messages = sorted(message_rows, key=lambda item: item.get('created_at') or started_at)
                        timestamps = [msg.get('created_at') for msg in messages if msg.get('created_at')]
                        timestamps.sort()
                        if len(timestamps) > 1:
                            gaps = [(timestamps[idx] - timestamps[idx - 1]).total_seconds() for idx in range(1, len(timestamps))]
                            average_gap_seconds = sum(gaps) / len(gaps) if gaps else 0
                except Exception:
                    average_gap_seconds = 0.0
            is_eligible, reasons = tracking.evaluate_lore_eligibility(
                message_count=message_count,
                participant_count=participant_count,
                duration_seconds=duration_seconds,
                average_gap_seconds=average_gap_seconds,
            )
            channel_name = row.get('channel_name') or f"Channel {row.get('channel_id') or 'unknown'}"
            lines = [
                f"{row.get('id')}.",
                channel_name,
                f"{participant_count} participants",
                f"{message_count} messages",
                f"Duration: {self._format_duration(duration_seconds)}",
                f"{'✅ Lore Eligible' if is_eligible else '❌ Not Eligible'}",
            ]
            if not is_eligible:
                lines.append("Reason:")
                lines.extend(f"• {reason}" for reason in reasons)
            embed.add_field(name="\u200b", value="\n".join(lines), inline=False)

        await send_output(
            ctx,
            embed=embed,
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    async def _send_conversation_detail_embed(self, ctx: commands.Context, detail: dict):
        started_at = detail.get('started_at')
        ended_at = detail.get('ended_at')
        duration_seconds = 0
        if started_at and ended_at:
            duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
        message_count = detail.get('message_count', 0)
        participants = detail.get('participants') or []
        message_rows = detail.get('messages') or []
        is_eligible, reasons = tracking.evaluate_lore_eligibility(
            message_count=message_count,
            participant_count=len(participants),
            duration_seconds=duration_seconds,
            average_gap_seconds=self._calculate_average_gap(message_rows, started_at),
        )
        embed = discord.Embed(
            title="🎬 Director's Dailies",
            description=f"Conversation #{detail.get('id')}",
            color=discord.Color(0x7B61FF),
        )
        embed.add_field(name="Channel", value=detail.get('channel_name') or f"Channel {detail.get('channel_id') or 'unknown'}", inline=False)
        embed.add_field(name="Started", value=self._format_timestamp(started_at), inline=True)
        embed.add_field(name="Ended", value=self._format_timestamp(ended_at), inline=True)
        embed.add_field(name="Duration", value=self._format_duration(duration_seconds), inline=True)
        embed.add_field(name="Participants", value="\n".join(participants) if participants else "No participants recorded", inline=False)
        embed.add_field(name="Messages", value=str(message_count), inline=True)
        embed.add_field(name="Lore Eligible", value="✅ Yes" if is_eligible else "❌ No", inline=True)
        if reasons:
            embed.add_field(name="Reasons", value="\n".join(f"• {reason}" for reason in reasons), inline=False)
        transcript = self._build_transcript_preview(message_rows)
        embed.add_field(name="Transcript Preview", value=transcript, inline=False)
        await send_output(
            ctx,
            embed=embed,
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    def _build_transcript_preview(self, messages: list, limit: int = 30, max_chars: int = 900) -> str:
        preview_messages = messages[:limit]
        lines = []
        for message in preview_messages:
            username = message.get('username') or 'Unknown'
            content = message.get('content') or ''
            lines.append(f"{username}: {content}")
        if len(messages) > limit:
            lines.append("... additional messages omitted")
        preview = "\n".join(lines)
        if len(preview) > max_chars:
            preview = preview[:max_chars].rsplit("\n", 1)[0] + "\n... additional messages omitted"
        return preview or "No transcript available."

    def _calculate_average_gap(self, messages: list, started_at: datetime | None) -> float:
        timestamps = [msg.get('created_at') for msg in messages if msg.get('created_at')]
        timestamps.sort()
        if len(timestamps) > 1:
            gaps = [(timestamps[idx] - timestamps[idx - 1]).total_seconds() for idx in range(1, len(timestamps))]
            return sum(gaps) / len(gaps) if gaps else 0.0
        return 0.0

    def _format_duration(self, seconds: int) -> str:
        minutes, remainder = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {remainder}s"
        if minutes:
            return f"{minutes}m {remainder}s"
        return f"{seconds}s"

    def _format_timestamp(self, value: datetime | None) -> str:
        if not value:
            return "Unknown"
        return value.strftime("%I:%M %p")

    @commands.command(name="reloadscheduler")
    async def reloadscheduler(self, ctx: commands.Context):
        if not await self._ensure_owner(ctx):
            return
        scheduler.initialize(self.bot)
        await scheduler.start()
        await send_output(
            ctx,
            content="Scheduler reloaded.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

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
        await send_output(
            ctx,
            content=f"{member.mention} has been promoted to {role.mention}.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    @commands.command(name="demote")
    async def demote(self, ctx: commands.Context, member: discord.Member):
        if not await self._ensure_owner(ctx):
            return
        for role_id in progression.PROGRESSION_ROLES:
            role = ctx.guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Studio admin demotion")
        await database.set_user_role(member.id, None)
        await send_output(
            ctx,
            content=f"{member.mention} has been demoted from progression roles.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

    @commands.command(name="resetscreentime")
    async def resetscreentime(self, ctx: commands.Context, member: discord.Member):
        if not await self._ensure_owner(ctx):
            return
        await database.reset_user_screen_time(member.id)
        await send_output(
            ctx,
            content=f"{member.mention}'s screen time has been reset.",
            message_type=MessageType.COMMAND_RESPONSE,
            module="cogs.studio_management",
            channel=ctx.channel,
        )

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
        end_time = utc_now()
        start_time = end_time - timedelta(hours=24)
        progress_task = StudioGenerationTask(
            ctx,
            title="🎬 MI BOMBO Studios",
            description="The Editorial Team has entered the newsroom...\n\nPreparing today's edition of the MI BOMBO Times.",
            stages=[
                "Initializing production...",
                "Collecting conversation footage...",
                "Reviewing today's events...",
                "Writing today's edition...",
                "Generating artwork...",
                "Finalizing newspaper...",
            ],
            footer="MI BOMBO Studios | Manual Preview",
        )
        await progress_task.start()
        image_path = None
        try:
            await progress_task.update_stage("Collecting conversation footage...")
            conversations = await studio_editor_pipeline.get_eligible_conversations(start_time, end_time)
            if not conversations:
                await progress_task.fail("No eligible conversations were found for a newspaper preview.")
                return

            await progress_task.update_stage("Reviewing today's events...")
            conversation_summaries = await studio_editor_pipeline.summarize_conversations(conversations)
            if not conversation_summaries:
                await progress_task.fail("No eligible conversation summaries could be generated for a newspaper preview.")
                return

            newspaper_json = await studio_editor_pipeline.generate_final_newspaper_json(conversation_summaries)
            if not newspaper_json:
                await progress_task.fail("The studio could not generate a newspaper preview right now.")
                return

            await progress_task.update_stage("Writing today's edition...")
            try:
                data = json.loads(newspaper_json)
            except json.JSONDecodeError:
                await progress_task.fail("The studio received an invalid newspaper draft.")
                return

            await progress_task.update_stage("Generating artwork...")
            image_prompt = data.get("image_prompt")
            if image_prompt:
                image_path = await image_provider.generate_image(image_prompt)
            
            await database.save_studio_content("newspaper", json.dumps(data))
            embed = self._build_newspaper_embed(data, image_path)

            await progress_task.update_stage("Finalizing newspaper...")
            await progress_task.complete(embed)
        except Exception as exc:
            logger.exception("Failed to generate newspaper preview")
            await progress_task.fail(str(exc) or "Unexpected error")
        finally:
            if image_path:
                image_provider.cleanup_temp_file(image_path)

    async def _generate_and_preview_weekly_cast(self, ctx: commands.Context):
        end_time = utc_now()
        start_time = end_time - timedelta(days=7)
        progress_task = StudioGenerationTask(
            ctx,
            title="🎬 MI BOMBO Studios",
            description="The Editorial Team is assembling this week's spotlight cast...",
            stages=[
                "Initializing production...",
                "Collecting conversation footage...",
                "Reviewing this week's highlights...",
                "Writing this week's cast...",
                "Generating artwork...",
                "Finalizing cast...",
            ],
            footer="MI BOMBO Studios | Manual Preview",
        )
        await progress_task.start()
        image_path = None
        try:
            await progress_task.update_stage("Collecting conversation footage...")
            messages = await database.get_messages_between(start_time, end_time)
            if not messages:
                await progress_task.fail("No recent messages were found for a weekly cast preview.")
                return

            await progress_task.update_stage("Reviewing this week's highlights...")
            cast_json = await text_provider.generate_weekly_cast_data(messages)
            if not cast_json:
                await progress_task.fail("The studio could not generate a weekly cast preview right now.")
                return

            await progress_task.update_stage("Writing this week's cast...")
            try:
                data = json.loads(cast_json)
            except json.JSONDecodeError:
                await progress_task.fail("The studio received an invalid weekly cast draft.")
                return

            await progress_task.update_stage("Generating artwork...")
            anime_prompt = data.get("anime_prompt")
            if anime_prompt:
                image_path = await image_provider.generate_image(anime_prompt)
            
            await database.save_studio_content("weekly_cast", json.dumps(data))
            embed = self._build_weekly_cast_embed(data, image_path)

            await progress_task.update_stage("Finalizing cast...")
            await progress_task.complete(embed)
        except Exception as exc:
            logger.exception("Failed to generate weekly cast preview")
            await progress_task.fail(str(exc) or "Unexpected error")
        finally:
            if image_path:
                image_provider.cleanup_temp_file(image_path)

    def _build_newspaper_embed(self, data: dict, image_path: Optional[str] = None) -> discord.Embed:
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
        if image_path:
            embed.set_image(file=discord.File(image_path))
        return embed

    def _build_weekly_cast_embed(self, data: dict, image_path: Optional[str] = None) -> discord.Embed:
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
        if image_path:
            embed.set_image(file=discord.File(image_path))
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(StudioManagementCog(bot))
