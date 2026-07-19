import logging

import discord
from discord.ext import commands

import database
import progression
import tracking
from config import EXCLUDED_TRACKING_CHANNELS

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
        if message.content.startswith("."):
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
            await tracker.track_message(
                message_id=message.id,
                user_id=message.author.id,
                content=message.content,
                channel_id=message.channel.id,
                timestamp=message.created_at,
                reply_to=reply_to,
            )

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
            screen_time_earned = progression.calculate_screen_time_bonuses(
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

    @commands.command(name="screentime", aliases=["st"])
    async def check_screen_time(self, ctx: commands.Context, member: discord.Member = None):
        """Check screen time for a member."""
        target = member or ctx.author

        try:
            user = await database.get_user(target.id)

            if not user:
                await ctx.send(f"No data found for {target.mention}")
                return

            screen_time = user['screen_time']
            current_role_id = user['current_role_id']

            # Get current role name
            role_name = "None"
            if current_role_id:
                role = ctx.guild.get_role(current_role_id)
                if role:
                    role_name = role.name

            embed = discord.Embed(
                title="📊 Screen Time",
                description=f"{target.mention}",
                color=discord.Color(0x7B61FF),
            )
            embed.add_field(name="Screen Time", value=f"**{screen_time}** points", inline=True)
            embed.add_field(name="Current Role", value=f"**{role_name}**", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error checking screen time for {target.id}: {e}")
            await ctx.send("Failed to check screen time.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MessageListenerCog(bot))
