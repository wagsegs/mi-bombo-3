import logging
import json
from datetime import datetime, timedelta

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

import database
from ai import image_provider, text_provider
from config import (
    MANUAL_STUDIO_MODE,
    SCHEDULER_TIMEZONE,
    NEWSPAPER_SCHEDULE,
    WEEKLY_CAST_SCHEDULE,
    NEWSPAPER_CHANNEL_ID,
    WEEKLY_CAST_CHANNEL_ID,
)
from utils import studio_editor_pipeline
from utils.output_gateway import MessageType, send_output
from utils.timezone import utc_now

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None
_bot: discord.ext.commands.Bot = None


def initialize(bot: discord.ext.commands.Bot) -> AsyncIOScheduler:
    """Initialize the scheduler."""
    global _scheduler, _bot
    _bot = bot
    _scheduler = AsyncIOScheduler(timezone=pytz.timezone(SCHEDULER_TIMEZONE))
    return _scheduler


async def start() -> None:
    """Start the scheduler."""
    if not _scheduler:
        raise RuntimeError("Scheduler not initialized. Call initialize() first.")
    
    try:
        _scheduler.start()
        logger.info("✓ Scheduler started")
        
        # Schedule jobs
        await schedule_newspaper()
        await schedule_weekly_cast()
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise


async def stop() -> None:
    """Stop the scheduler."""
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("✓ Scheduler stopped")


async def schedule_newspaper() -> None:
    """Schedule daily newspaper job."""
    if not _scheduler:
        return
    if MANUAL_STUDIO_MODE:
        logger.info("🛠️ Manual Studio mode enabled; automatic newspaper scheduling is disabled")
        return

    # Parse schedule (format: "HH:MM")
    hour, minute = map(int, NEWSPAPER_SCHEDULE.split(":"))
    
    _scheduler.add_job(
        _job_newspaper,
        CronTrigger(hour=hour, minute=minute),
        id="daily_newspaper",
        name="Daily Newspaper",
        replace_existing=True,
    )
    logger.info(f"✓ Scheduled newspaper at {NEWSPAPER_SCHEDULE} daily")


async def schedule_weekly_cast() -> None:
    """Schedule weekly cast job (Sundays)."""
    if not _scheduler:
        return
    if MANUAL_STUDIO_MODE:
        logger.info("🛠️ Manual Studio mode enabled; automatic weekly cast scheduling is disabled")
        return

    # Parse schedule (format: "HH:MM")
    hour, minute = map(int, WEEKLY_CAST_SCHEDULE.split(":"))
    
    _scheduler.add_job(
        _job_weekly_cast,
        CronTrigger(day_of_week="sun", hour=hour, minute=minute),
        id="weekly_cast",
        name="Weekly Cast",
        replace_existing=True,
    )
    logger.info(f"✓ Scheduled weekly cast for Sundays at {WEEKLY_CAST_SCHEDULE}")


async def _job_newspaper() -> None:
    """Daily newspaper job."""
    if MANUAL_STUDIO_MODE:
        logger.info("🛠️ Manual Studio mode enabled; newspaper job skipped")
        return
    try:
        logger.info("📰 Starting daily newspaper generation...")

        # Get eligible conversations from the last 24 hours
        end_time = utc_now()
        start_time = end_time - timedelta(hours=24)
        conversations = await studio_editor_pipeline.get_eligible_conversations(start_time, end_time)

        if not conversations:
            logger.warning("No eligible conversations found for newspaper")
            return

        conversation_summaries = await studio_editor_pipeline.summarize_conversations(conversations)
        if not conversation_summaries:
            logger.warning("No eligible conversation summaries found for newspaper")
            return

        newspaper_json = await studio_editor_pipeline.generate_final_newspaper_json(conversation_summaries)

        if not newspaper_json:
            logger.error("Failed to generate newspaper data")
            return

        # Parse JSON response
        try:
            data = json.loads(newspaper_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse newspaper JSON: {e}\n{newspaper_json}")
            return

        # Generate image
        image_prompt = data.get("image_prompt", "")
        image_path = await image_provider.generate_image(image_prompt)
        image_url = image_path or ""

        # Save to database
        await database.save_newspaper(
            headline=data.get("headline", "MI BOMBO Daily"),
            summary=data.get("summary", ""),
            funniest_moments=data.get("funniest_moments", ""),
            lore_updates=data.get("lore_updates", ""),
            cast_candidates=data.get("cast_candidates", ""),
            image_url=image_url or "",
        )

        # Post to Discord
        channel = _bot.get_channel(NEWSPAPER_CHANNEL_ID)
        if not channel:
            logger.error(f"Newspaper channel {NEWSPAPER_CHANNEL_ID} not found")
            return

        embed = discord.Embed(
            title=f"📰 {data.get('headline', 'MI BOMBO Daily')}",
            description=data.get("summary", ""),
            color=discord.Color(0x7B61FF),
        )

        if data.get("funniest_moments"):
            embed.add_field(
                name="😂 Funniest Moments",
                value=data.get("funniest_moments", ""),
                inline=False,
            )

        if data.get("lore_updates"):
            embed.add_field(
                name="📖 Lore Updates",
                value=data.get("lore_updates", ""),
                inline=False,
            )

        if data.get("cast_candidates"):
            embed.add_field(
                name="⭐ Cast Candidates",
                value=data.get("cast_candidates", ""),
                inline=False,
            )

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text="MI BOMBO Studios Daily Newspaper")
        await send_output(
            channel,
            embed=embed,
            message_type=MessageType.NEWSPAPER,
            module="scheduler",
            channel=channel,
        )

        logger.info("✓ Daily newspaper posted")

    except Exception as e:
        logger.exception(f"Failed to generate daily newspaper: {e}")


async def _job_weekly_cast() -> None:
    """Weekly cast job."""
    if MANUAL_STUDIO_MODE:
        logger.info("🛠️ Manual Studio mode enabled; weekly cast job skipped")
        return
    try:
        logger.info("🎭 Starting weekly cast generation...")

        # Get messages from last 7 days
        end_time = utc_now()
        start_time = end_time - timedelta(days=7)
        messages = await database.get_messages_between(start_time, end_time)

        if not messages:
            logger.warning("No messages found for weekly cast")
            return

        # Generate cast data with the text provider
        cast_json = await text_provider.generate_weekly_cast_data(messages)

        if not cast_json:
            logger.error("Failed to generate weekly cast data")
            return

        # Parse JSON response
        try:
            data = json.loads(cast_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cast JSON: {e}\n{cast_json}")
            return

        # Generate anime poster
        anime_prompt = data.get("anime_prompt", "")
        image_path = await image_provider.generate_image(anime_prompt)
        image_url = image_path or ""

        # Save to database
        cast_members = json.dumps(data.get("main_cast", []))
        anime_style = data.get("anime_style", "Unknown")

        await database.save_weekly_cast(
            week_of=start_time,
            members=cast_members,
            anime_style=anime_style,
            image_url=image_url or "",
        )

        # Post to Discord
        channel = _bot.get_channel(WEEKLY_CAST_CHANNEL_ID)
        if not channel:
            logger.error(f"Weekly cast channel {WEEKLY_CAST_CHANNEL_ID} not found")
            return

        embed = discord.Embed(
            title="🎭 This Week's Main Cast",
            description=f"Anime Style: **{anime_style}**",
            color=discord.Color(0x7B61FF),
        )

        for member in data.get("main_cast", []):
            value = (
                f"**Position:** {member.get('position', 'Unknown')}\n"
                f"**Character:** {member.get('character_description', 'TBD')}\n"
                f"**Reason:** {member.get('reason', 'Outstanding performance')}"
            )
            embed.add_field(
                name=f"{member.get('nickname', 'Unknown')} (@{member.get('username', 'unknown')})",
                value=value,
                inline=False,
            )

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text="MI BOMBO Studios Weekly Cast")
        await send_output(
            channel,
            embed=embed,
            message_type=MessageType.WEEKLY_CAST,
            module="scheduler",
            channel=channel,
        )

        logger.info("✓ Weekly cast posted")

    except Exception as e:
        logger.exception(f"Failed to generate weekly cast: {e}")
