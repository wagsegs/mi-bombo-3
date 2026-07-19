import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

import database
import progression
import tracking
from ai import gemini
from config import (
    EXCLUDED_TRACKING_CHANNELS,
    PREFIX,
    STUDIO_PREFIX,
    LORE_MIN_PARTICIPANTS,
    LORE_MIN_MESSAGES,
    LORE_MAX_AVERAGE_REPLY_GAP_SECONDS,
    LORE_MIN_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)

# Global conversation tracker instance
_conversation_tracker: tracking.ConversationTracker = None


def get_tracker() -> tracking.ConversationTracker:
    """Get the global conversation tracker."""
    global _conversation_tracker
    if _conversation_tracker is None:
        _conversation_tracker = tracking.ConversationTracker()
    return _conversation_tracker


class MessageListenerCog(commands.Cog):
    """Cog for tracking messages and managing screen time."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track all non-bot messages and award screen time."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore webhook messages
        if message.webhook_id:
            return

        # Ignore excluded tracking channels
        if message.channel.id in EXCLUDED_TRACKING_CHANNELS:
            return

        # Ignore command messages
        if message.content.startswith((PREFIX, STUDIO_PREFIX, ".")):
            return

        try:
            # Ensure user exists in database
            await database.get_or_create_user(
                user_id=message.author.id,
                username=message.author.name,
                nickname=message.author.display_name,
            )

            # Track message in database
            attachments = [att.url for att in message.attachments] if message.attachments else []
            reply_to = message.reference.message_id if message.reference else None

            await database.save_message(
                message_id=message.id,
                user_id=message.author.id,
                username=message.author.name,
                nickname=message.author.display_name,
                channel_id=message.channel.id,
                channel_name=getattr(message.channel, "name", "DM"),
                content=message.content,
                attachments=attachments,
                reply_to_message_id=reply_to,
            )

            # Track in conversation tracker
            tracker = get_tracker()
            conversation = await tracker.track_message(
                message_id=message.id,
                user_id=message.author.id,
                content=message.content,
                channel_id=message.channel.id,
                timestamp=message.created_at,
                reply_to=reply_to,
            )

            if conversation is not None:
                await database.save_conversation_snapshot(
                    conversation_id=conversation.id,
                    channel_id=conversation.channel_id,
                    channel_name=getattr(message.channel, "name", "DM"),
                    started_at=conversation.started_at,
                    ended_at=conversation.last_message_time,
                    message_ids=conversation.message_ids,
                    participant_ids=list(conversation.participant_ids),
                )

            await self._process_lore_candidates(message, reply_to)

            # Calculate screen time based on message quality
            message_length = len(message.content)

            # Count conversation participants (rough estimate from recent messages in channel)
            recent_messages = []
            try:
                async for msg in message.channel.history(limit=50):
                    if not msg.author.bot:
                        recent_messages.append(msg.author.id)
            except (discord.Forbidden, discord.HTTPException):
                recent_messages = [message.author.id]

            num_participants = len(set(recent_messages))

            # Calculate screen time
            screen_time_earned = await progression.calculate_screen_time_bonuses(
                message_length=message_length,
                conversation_participants=num_participants,
                is_reply=reply_to is not None,
            )

            if screen_time_earned > 0:
                new_total = await database.update_screen_time(
                    user_id=message.author.id,
                    amount=screen_time_earned,
                    reason="message",
                )

                # Check if they should be promoted
                if message.guild:
                    new_role = await progression.check_and_promote(
                        message.guild,
                        message.author,
                    )

                    if new_role:
                        # Send casting update
                        from config import CASTING_CHANNEL_ID
                        casting_channel = self.bot.get_channel(CASTING_CHANNEL_ID)

                        if casting_channel:
                            embed = await progression.create_casting_update_embed(
                                message.author,
                                new_role,
                            )
                            try:
                                await casting_channel.send(embed=embed)
                            except discord.Forbidden:
                                logger.error(f"Missing permissions to post in casting channel {CASTING_CHANNEL_ID}")
                            except Exception as e:
                                logger.error(f"Failed to post casting update: {e}")

        except Exception as e:
            logger.exception(f"Error processing message {message.id}: {e}")

    async def _process_lore_candidates(self, message: discord.Message, reply_to: int | None):
        active_session = await database.get_active_lore_session(message.guild.id if message.guild else 0)
        if not active_session:
            return

        if message.channel.id != active_session['channel_id']:
            return

        recent_messages = []
        try:
            async for past_message in message.channel.history(limit=50):
                if not past_message.author.bot:
                    recent_messages.append(past_message)
        except (discord.Forbidden, discord.HTTPException):
            recent_messages = [message]

        participant_ids = {msg.author.id for msg in recent_messages if not msg.author.bot}
        timestamps = [msg.created_at for msg in recent_messages]
        timestamps.sort()
        if len(timestamps) > 1:
            gaps = [
                (timestamps[idx] - timestamps[idx - 1]).total_seconds()
                for idx in range(1, len(timestamps))
            ]
            average_gap = sum(gaps) / len(gaps) if gaps else 0
        else:
            average_gap = 0
        duration_seconds = (timestamps[-1] - timestamps[0]).total_seconds() if len(timestamps) > 1 else 0

        is_eligible, reasons = tracking.evaluate_lore_eligibility(
            message_count=len(recent_messages),
            participant_count=len(participant_ids),
            duration_seconds=int(duration_seconds),
            average_gap_seconds=average_gap,
        )
        if not is_eligible:
            return

        source_ids = [msg.id for msg in recent_messages if not msg.author.bot]
        if not source_ids:
            return

        lore_text = await gemini.generate_lore_update([
            {
                'username': msg.author.name,
                'content': msg.content,
                'created_at': msg.created_at,
                'user_id': msg.author.id,
            }
            for msg in recent_messages
            if not msg.author.bot
        ])

        if lore_text:
            await database.save_lore(lore_text, source_ids)

    @commands.command(name="screentime", aliases=["st"])
    async def check_screen_time(self, ctx: commands.Context, member: discord.Member = None):
        """Show a cinematic production status for a member."""
        target = member or ctx.author

        try:
            user = await database.get_user(target.id)
            if not user:
                await ctx.send(f"No data found for {target.mention}")
                return

            screen_time = user.get('screen_time', 0) or 0
            current_role_id = user.get('current_role_id')
            role_name = progression.get_role_name(current_role_id, ctx.guild)
            rank_name = progression.get_rank_name(current_role_id, ctx.guild)
            status_text = progression.get_promotion_status(screen_time, current_role_id)

            embed = discord.Embed(
                title="🎬 Studio Status",
                description=f"{target.mention}",
                color=discord.Color(0x7B61FF),
            )
            embed.add_field(name="Current Role", value=f"**{role_name}**", inline=True)
            embed.add_field(name="Current Production Status", value=f"**{status_text}**", inline=True)
            embed.add_field(name="Current Progression Role", value=f"**{role_name}**", inline=True)
            embed.add_field(name="Current Rank", value=f"**{rank_name}**", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error checking screen time for {target.id}: {e}")
            await ctx.send("Failed to check screen time.")

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        """Show a cinematic leaderboard without exposing raw stats."""
        try:
            members = await database.get_users_by_screen_time_threshold(0)
            if not members:
                await ctx.send("The studio has not recorded enough performances yet.")
                return

            async def message_count_for(user_id: int) -> int:
                rows = await database.get_messages_between(datetime.utcnow() - timedelta(days=30), datetime.utcnow())
                return sum(1 for row in rows if row.get('user_id') == user_id)

            ranked = []
            for user in members:
                count = await message_count_for(user['user_id'])
                ranked.append((user, count))

            ranked.sort(key=lambda item: (item[0].get('screen_time', 0), item[1]), reverse=True)
            top = ranked[:5]

            embed = discord.Embed(
                title="🎬 Studio Leaderboard",
                description="The studio's brightest performances.",
                color=discord.Color(0x7B61FF),
            )
            for index, (user, _) in enumerate(top, start=1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(index, f"{index}.")
                role_name = progression.get_role_name(user.get('current_role_id'), ctx.guild)
                embed.add_field(name=f"{medal} {user.get('nickname') or user.get('username')}", value=role_name, inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error generating leaderboard: {e}")
            await ctx.send("Failed to generate the studio leaderboard.")

    @commands.command(name="profile")
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        """Show a cinematic actor profile."""
        target = member or ctx.author
        try:
            user = await database.get_user(target.id)
            if not user:
                await ctx.send(f"No profile found for {target.mention}")
                return

            role_name = progression.get_role_name(user.get('current_role_id'), ctx.guild)
            status_text = progression.get_promotion_status(user.get('screen_time', 0), user.get('current_role_id'))
            joined = user.get('created_at')
            joined_text = joined.strftime('%Y-%m-%d') if isinstance(joined, datetime) else 'Unknown'

            promotion_history = await database.get_user_promotion_history(target.id)
            promotion_text = ", ".join(
                f"{row['to_role_id']}" for row in promotion_history[:3]
            ) if promotion_history else "No promotions yet"

            weekly_casts = await database.get_weekly_cast_appearances(target.id)
            weekly_cast_text = ", ".join(weekly_casts[:3]) if weekly_casts else "No weekly cast appearances yet"

            newspaper_features = await database.get_newspaper_features(target.id)
            newspaper_text = ", ".join(newspaper_features[:3]) if newspaper_features else "No newspaper features yet"

            embed = discord.Embed(
                title=f"🎭 {target.display_name}",
                description="A cinematic profile for the studio's cast.",
                color=discord.Color(0x7B61FF),
            )
            embed.add_field(name="Actor Name", value=f"**{target.display_name}**", inline=True)
            embed.add_field(name="Current Role", value=f"**{role_name}**", inline=True)
            embed.add_field(name="Current Production Status", value=f"**{status_text}**", inline=False)
            embed.add_field(name="Joined Production", value=f"**{joined_text}**", inline=True)
            embed.add_field(name="Promotion History", value=f"**{promotion_text}**", inline=True)
            embed.add_field(name="Weekly Cast Appearances", value=f"**{weekly_cast_text}**", inline=False)
            embed.add_field(name="Newspaper Features", value=f"**{newspaper_text}**", inline=False)
            embed.set_thumbnail(url=target.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error generating profile for {target.id}: {e}")
            await ctx.send("Failed to generate the actor profile.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MessageListenerCog(bot))
