import logging
import random
from typing import Optional, List

import discord
from discord.ext import commands

import database
from config import PROGRESSION_ROLES, SCREEN_TIME_THRESHOLDS

logger = logging.getLogger(__name__)


async def calculate_screen_time_bonuses(
    message_length: int,
    conversation_participants: int,
    is_reply: bool = False,
) -> int:
    """
    Calculate screen time bonuses modularly.
    
    Args:
        message_length: Length of the message in characters
        conversation_participants: Number of participants in the conversation
        is_reply: Whether the message is a reply
    
    Returns:
        Total screen time earned
    """
    total = 0
    total += conversation_bonus(message_length)
    total += participant_bonus(conversation_participants)
    total += length_bonus(message_length)
    if is_reply:
        total += revival_bonus()
    # Future bonuses can be added here:
    # total += future_ai_bonus()
    # total += future_reaction_bonus()
    return total


def conversation_bonus(message_length: int) -> int:
    """Bonus for participating in conversations."""
    if message_length >= 100:
        return 5
    elif message_length >= 50:
        return 3
    elif message_length >= 10:
        return 1
    return 0


def participant_bonus(num_participants: int) -> int:
    """Bonus for conversations with multiple participants."""
    if num_participants >= 5:
        return 5
    elif num_participants >= 3:
        return 3
    elif num_participants >= 2:
        return 1
    return 0


def length_bonus(message_length: int) -> int:
    """Bonus for longer messages."""
    if message_length >= 300:
        return 5
    elif message_length >= 150:
        return 3
    elif message_length >= 50:
        return 1
    return 0


def revival_bonus() -> int:
    """Bonus for reviving dead conversations (replying to old messages)."""
    return 2


def future_ai_bonus() -> int:
    """Placeholder for future AI-based bonuses."""
    return 0


def future_reaction_bonus() -> int:
    """Placeholder for future reaction-based bonuses."""
    return 0


async def check_and_promote(guild: discord.Guild, member: discord.Member) -> Optional[discord.Role]:
    """
    Check if a user should be promoted based on screen time.
    
    Args:
        guild: The Discord guild
        member: The member to check
    
    Returns:
        The new role if promoted, None otherwise
    """
    user = await database.get_user(member.id)
    if not user:
        return None

    screen_time = user['screen_time']

    # Find the highest role they should have based on screen time
    target_role_id = None
    for role_id in reversed(PROGRESSION_ROLES):
        threshold = SCREEN_TIME_THRESHOLDS.get(role_id, 0)
        if screen_time >= threshold:
            target_role_id = role_id
            break

    if not target_role_id:
        return None

    # Check if they already have this role
    if user['current_role_id'] == target_role_id:
        return None

    # Remove all progression roles
    for role_id in PROGRESSION_ROLES:
        role = guild.get_role(role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Progression system: removing old progression role")
            except discord.Forbidden:
                logger.error(f"Missing permissions to remove role {role_id} from {member.id}")
            except Exception as e:
                logger.error(f"Failed to remove role {role_id} from {member.id}: {e}")

    # Add new role
    new_role = guild.get_role(target_role_id)
    if not new_role:
        logger.error(f"Target role {target_role_id} not found in guild")
        return None

    try:
        await member.add_roles(new_role, reason="Progression system: promotion")
        logger.info(f"Promoted {member.id} to role {target_role_id}")

        # Record in database
        old_role_id = user['current_role_id']
        await database.promote_user(member.id, old_role_id, target_role_id)

        return new_role
    except discord.Forbidden:
        logger.error(f"Missing permissions to add role {target_role_id} to {member.id}")
        return None
    except Exception as e:
        logger.error(f"Failed to promote {member.id}: {e}")
        return None


async def create_casting_update_embed(member: discord.Member, new_role: discord.Role) -> discord.Embed:
    """
    Create a cinematic casting update embed.
    
    Args:
        member: The promoted member
        new_role: Their new role
    
    Returns:
        Discord Embed object
    """
    messages = [
        f"🎬 {member.mention} has been cast as **{new_role.name}**!",
        f"✨ {member.mention} is now **{new_role.name}**!",
        f"🎭 {member.mention} has ascended to **{new_role.name}**!",
        f"🏆 {member.mention} earned the role of **{new_role.name}**!",
        f"⭐ {member.mention} is officially **{new_role.name}** now!",
    ]

    message = random.choice(messages)

    # Get user's screen time
    user = await database.get_user(member.id)
    screen_time = user['screen_time'] if user else 0

    embed = discord.Embed(
        title="🎬 CASTING UPDATE",
        description=message,
        color=new_role.color if new_role.color != discord.Color.default() else discord.Color(0x7B61FF),
    )
    embed.add_field(name="Screen Time", value=f"{screen_time} points", inline=True)
    embed.add_field(name="Role", value=new_role.mention, inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="MI BOMBO Studios | Director's Cast")

    return embed


class ProgressionCog(commands.Cog):
    """Cog for handling progression and promotions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="checkprogression", hidden=True)
    @commands.is_owner()
    async def check_progression(self, ctx: commands.Context):
        """Check progression for current member (owner only)."""
        member = ctx.author
        guild = ctx.guild

        if not guild:
            await ctx.send("This command only works in a guild.")
            return

        new_role = await check_and_promote(guild, member)

        if new_role:
            embed = await create_casting_update_embed(member, new_role)
            await ctx.send(embed=embed)
        else:
            user = await database.get_user(member.id)
            screen_time = user['screen_time'] if user else 0
            await ctx.send(f"No promotion available. Current screen time: {screen_time}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ProgressionCog(bot))
