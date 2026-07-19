import logging
import random
from typing import Optional, List

import discord
from discord.ext import commands

import database
from config import PROGRESSION_ROLES, SCREEN_TIME_THRESHOLDS
from utils.output_gateway import MessageType, send_output

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
    total += base_message_bonus(message_length)
    total += participant_bonus(conversation_participants)
    if is_reply:
        total += reply_bonus()
    # Future bonuses can be added here:
    # total += future_ai_bonus()
    # total += future_reaction_bonus()
    # total += future_conversation_momentum_bonus()
    return total


def base_message_bonus(message_length: int) -> int:
    """Reward meaningful participation without double-counting message length."""
    if message_length >= 250:
        return 3
    if message_length >= 100:
        return 2
    if message_length >= 10:
        return 1
    return 0


def participant_bonus(num_participants: int) -> int:
    """Bonus for conversations with multiple participants."""
    if num_participants >= 5:
        return 1
    if num_participants >= 3:
        return 1
    if num_participants >= 2:
        return 1
    return 0


def reply_bonus() -> int:
    """Small bonus for replying to an active conversation.

    A true revival bonus should be implemented later when a message restarts an
    inactive conversation after a configurable amount of time.
    """
    return 1


def future_ai_bonus() -> int:
    """Placeholder for future AI-based bonuses."""
    return 0


def future_reaction_bonus() -> int:
    """Placeholder for future reaction-based bonuses."""
    return 0


def get_role_name(role_id: Optional[int], guild: Optional[discord.Guild]) -> str:
    """Return a role name for display, falling back to a cinematic label."""
    if not role_id or not guild:
        return "Rising Talent"
    role = guild.get_role(role_id)
    return role.name if role else "Rising Talent"


def get_rank_name(role_id: Optional[int], guild: Optional[discord.Guild]) -> str:
    """Return a rank label suitable for the Studio UI."""
    if not role_id or not guild:
        return "Newcomer"
    role = guild.get_role(role_id)
    if not role:
        return "Newcomer"
    name = role.name.lower()
    if "main character" in name:
        return "Lead"
    if "main cast" in name:
        return "Principal"
    if "supporting" in name:
        return "Supporting"
    if "guest" in name:
        return "Featured"
    if "extra" in name:
        return "Background"
    return "Featured"


def get_promotion_status(screen_time: int, role_id: Optional[int]) -> str:
    """Return a cinematic status message based on how close a member is to the next promotion."""
    if role_id is None:
        return "The Director has been noticing you."

    next_threshold = None
    for current_role_id in PROGRESSION_ROLES:
        if current_role_id == role_id:
            continue
        threshold = SCREEN_TIME_THRESHOLDS.get(current_role_id, 0)
        if threshold > screen_time:
            next_threshold = threshold
            break

    if next_threshold is None:
        return "The Director has been noticing you."

    if next_threshold - screen_time <= 100:
        return "One good performance away."
    if next_threshold - screen_time <= 300:
        return "Almost ready for promotion."
    if next_threshold - screen_time <= 700:
        return "Making steady progress."
    return "Stealing more scenes every day."


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

    # Get user's progression status for a cinematic promotion update.
    user = await database.get_user(member.id)
    screen_time = user['screen_time'] if user else 0
    status = get_promotion_status(screen_time, None)

    embed = discord.Embed(
        title="🎬 CASTING UPDATE",
        description=message,
        color=new_role.color if new_role.color != discord.Color.default() else discord.Color(0x7B61FF),
    )
    embed.add_field(name="Production Status", value=status, inline=False)
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
            await send_output(
                ctx,
                content="This command only works in a guild.",
                message_type=MessageType.COMMAND_RESPONSE,
                module="progression",
                channel=ctx.channel,
            )
            return

        new_role = await check_and_promote(guild, member)

        if new_role:
            embed = await create_casting_update_embed(member, new_role)
            await send_output(
                ctx,
                embed=embed,
                message_type=MessageType.PROMOTION,
                module="progression",
                channel=ctx.channel,
            )
        else:
            user = await database.get_user(member.id)
            screen_time = user['screen_time'] if user else 0
            await send_output(
                ctx,
                content=f"No promotion available. Current screen time: {screen_time}",
                message_type=MessageType.COMMAND_RESPONSE,
                module="progression",
                channel=ctx.channel,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProgressionCog(bot))
