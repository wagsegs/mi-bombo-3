import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def connect(database_url: str) -> None:
    """Initialize connection pool to PostgreSQL database."""
    global _pool
    try:
        _pool = await asyncpg.create_pool(database_url, min_size=10, max_size=20)
        logger.info("✓ Database connected")
        await initialize_tables()
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        raise


async def disconnect() -> None:
    """Close database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("✓ Database disconnected")


async def _get_connection():
    """Get a connection from the pool."""
    if not _pool:
        raise RuntimeError("Database not connected. Call connect() first.")
    return await _pool.acquire()


async def initialize_tables() -> None:
    """Create tables if they don't exist."""
    conn = await _get_connection()
    try:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT NOT NULL,
                nickname TEXT,
                current_role_id BIGINT,
                screen_time INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id BIGINT PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                username TEXT NOT NULL,
                nickname TEXT,
                channel_id BIGINT NOT NULL,
                channel_name TEXT NOT NULL,
                content TEXT,
                attachments TEXT[],
                reply_to_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Screen time table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS screen_time (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                amount INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Promotions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                from_role_id BIGINT,
                to_role_id BIGINT NOT NULL,
                screen_time_at_promotion INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Newspapers table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS newspapers (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL UNIQUE,
                headline TEXT,
                summary TEXT,
                funniest_moments TEXT,
                lore_updates TEXT,
                cast_candidates TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Lore table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lore (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                content TEXT,
                source_messages TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Weekly cast table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_cast (
                id SERIAL PRIMARY KEY,
                week_of DATE NOT NULL,
                members TEXT NOT NULL,
                anime_style TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Lore sessions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lore_sessions (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                started_by BIGINT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Manual studio content table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS studio_content (
                id SERIAL PRIMARY KEY,
                content_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP
            )
        """)

        # Conversations table for tracking conversation groups
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                topic TEXT,
                message_ids BIGINT[],
                participant_ids BIGINT[],
                channel_id BIGINT,
                channel_name TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS channel_id BIGINT")
        await conn.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS channel_name TEXT")

        logger.info("✓ Database tables initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize tables: {e}")
        raise
    finally:
        await _pool.release(conn)


async def save_message(
    message_id: int,
    user_id: int,
    username: str,
    nickname: Optional[str],
    channel_id: int,
    channel_name: str,
    content: Optional[str],
    attachments: Optional[List[str]] = None,
    reply_to_message_id: Optional[int] = None,
) -> None:
    """Save a message to the database."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO messages (
                message_id, user_id, username, nickname,
                channel_id, channel_name, content, attachments, reply_to_message_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (message_id) DO NOTHING
        """, message_id, user_id, username, nickname, channel_id,
            channel_name, content, attachments or [], reply_to_message_id)
    except Exception as e:
        logger.error(f"Failed to save message {message_id}: {e}")
    finally:
        await _pool.release(conn)


async def get_or_create_user(user_id: int, username: str, nickname: Optional[str] = None) -> None:
    """Create a user if they don't exist, or update their info."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO users (user_id, username, nickname)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
            SET username = $2, nickname = $3, updated_at = CURRENT_TIMESTAMP
        """, user_id, username, nickname)
    except Exception as e:
        logger.error(f"Failed to create/update user {user_id}: {e}")
    finally:
        await _pool.release(conn)


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data by ID."""
    conn = await _get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        return None
    finally:
        await _pool.release(conn)


async def save_conversation_snapshot(
    conversation_id: int,
    channel_id: int,
    channel_name: str,
    started_at: datetime,
    ended_at: datetime,
    message_ids: List[int],
    participant_ids: List[int],
) -> None:
    """Persist a tracked conversation summary to the database."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO conversations (
                id, channel_id, channel_name, message_ids, participant_ids, started_at, ended_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                channel_name = EXCLUDED.channel_name,
                message_ids = EXCLUDED.message_ids,
                participant_ids = EXCLUDED.participant_ids,
                started_at = EXCLUDED.started_at,
                ended_at = EXCLUDED.ended_at
        """, conversation_id, channel_id, channel_name, message_ids, participant_ids, started_at, ended_at)
    except Exception as e:
        logger.error(f"Failed to save conversation snapshot {conversation_id}: {e}")
    finally:
        await _pool.release(conn)


async def get_recent_conversation_summaries(limit: int = 5) -> List[Dict[str, Any]]:
    """Return the most recently started conversations from the database."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch("""
            SELECT id, channel_id, channel_name, started_at, ended_at, message_ids, participant_ids
            FROM conversations
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get recent conversations: {e}")
        return []
    finally:
        await _pool.release(conn)


async def get_conversation_detail(conversation_id: int) -> Optional[Dict[str, Any]]:
    """Return a detailed conversation payload including its stored transcript."""
    conn = await _get_connection()
    try:
        row = await conn.fetchrow("""
            SELECT id, channel_id, channel_name, started_at, ended_at, message_ids, participant_ids
            FROM conversations
            WHERE id = $1
        """, conversation_id)
        if not row:
            return None
        message_ids = list(row['message_ids'] or [])
        participant_ids = list(row['participant_ids'] or [])
        messages = []
        if message_ids:
            message_rows = await conn.fetch("""
                SELECT username, content, created_at
                FROM messages
                WHERE message_id = ANY($1::BIGINT[])
                ORDER BY created_at ASC, message_id ASC
            """, message_ids)
            messages = [dict(msg) for msg in message_rows]
        user_rows = await conn.fetch("""
            SELECT user_id, username, nickname FROM users WHERE user_id = ANY($1::BIGINT[])
        """, participant_ids) if participant_ids else []
        users_by_id = {
            row['user_id']: row['nickname'] or row['username']
            for row in user_rows
        }
        payload = dict(row)
        payload['message_count'] = len(message_ids)
        payload['participant_count'] = len(participant_ids)
        payload['participants'] = [users_by_id.get(user_id, str(user_id)) for user_id in participant_ids]
        payload['messages'] = messages
        return payload
    except Exception as e:
        logger.error(f"Failed to get conversation detail {conversation_id}: {e}")
        return None
    finally:
        await _pool.release(conn)


async def update_screen_time(user_id: int, amount: int, reason: str = "conversation") -> int:
    """Add screen time to a user and return new total."""
    conn = await _get_connection()
    try:
        # Insert screen time record
        await conn.execute("""
            INSERT INTO screen_time (user_id, amount, reason)
            VALUES ($1, $2, $3)
        """, user_id, amount, reason)

        # Get updated total
        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) as total FROM screen_time WHERE user_id = $1",
            user_id
        )
        new_total = row['total'] if row else 0

        # Update user's screen_time field
        await conn.execute(
            "UPDATE users SET screen_time = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2",
            new_total, user_id
        )

        return new_total
    except Exception as e:
        logger.error(f"Failed to update screen time for user {user_id}: {e}")
        return 0
    finally:
        await _pool.release(conn)


async def promote_user(user_id: int, from_role_id: Optional[int], to_role_id: int) -> None:
    """Record a promotion in the database."""
    conn = await _get_connection()
    try:
        # Get current screen time
        user = await get_user(user_id)
        screen_time_at_promotion = user['screen_time'] if user else 0

        # Record promotion
        await conn.execute("""
            INSERT INTO promotions (user_id, from_role_id, to_role_id, screen_time_at_promotion)
            VALUES ($1, $2, $3, $4)
        """, user_id, from_role_id, to_role_id, screen_time_at_promotion)

        # Update user's current role
        await conn.execute(
            "UPDATE users SET current_role_id = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2",
            to_role_id, user_id
        )
    except Exception as e:
        logger.error(f"Failed to record promotion for user {user_id}: {e}")
    finally:
        await _pool.release(conn)


async def get_messages_between(start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """Get all messages in a time range."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch("""
            SELECT * FROM messages
            WHERE created_at >= $1 AND created_at <= $2
            ORDER BY created_at ASC
        """, start_time, end_time)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        return []
    finally:
        await _pool.release(conn)


async def save_newspaper(
    headline: str,
    summary: str,
    funniest_moments: str,
    lore_updates: str,
    cast_candidates: str,
    image_url: str,
) -> None:
    """Save newspaper data to database."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO newspapers (headline, summary, funniest_moments, lore_updates, cast_candidates, image_url, date)
            VALUES ($1, $2, $3, $4, $5, $6, CURRENT_DATE)
            ON CONFLICT (date) DO UPDATE
            SET headline = $1, summary = $2, funniest_moments = $3,
                lore_updates = $4, cast_candidates = $5, image_url = $6
        """, headline, summary, funniest_moments, lore_updates, cast_candidates, image_url)
    except Exception as e:
        logger.error(f"Failed to save newspaper: {e}")
    finally:
        await _pool.release(conn)


async def save_lore(content: str, source_messages: List[int]) -> None:
    """Save lore data to database."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO lore (date, content, source_messages)
            VALUES (CURRENT_DATE, $1, $2)
        """, content, source_messages)
    except Exception as e:
        logger.error(f"Failed to save lore: {e}")
    finally:
        await _pool.release(conn)


async def start_lore_session(guild_id: int, channel_id: int, started_by: int) -> bool:
    """Start a new lore recording session if one is not already active."""
    conn = await _get_connection()
    try:
        existing = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM lore_sessions WHERE is_active = TRUE)"
        )
        if existing:
            return False

        await conn.execute(
            "INSERT INTO lore_sessions (guild_id, channel_id, started_by, is_active) VALUES ($1, $2, $3, TRUE)",
            guild_id,
            channel_id,
            started_by,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to start lore session: {e}")
        return False
    finally:
        await _pool.release(conn)


async def stop_lore_session(guild_id: int) -> bool:
    """Stop the active lore session for a guild."""
    conn = await _get_connection()
    try:
        result = await conn.execute(
            "UPDATE lore_sessions SET is_active = FALSE, ended_at = CURRENT_TIMESTAMP WHERE guild_id = $1 AND is_active = TRUE",
            guild_id,
        )
        return "UPDATE 1" in result
    except Exception as e:
        logger.error(f"Failed to stop lore session: {e}")
        return False
    finally:
        await _pool.release(conn)


async def get_active_lore_session(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get the currently active lore session for a guild."""
    conn = await _get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM lore_sessions WHERE guild_id = $1 AND is_active = TRUE ORDER BY started_at DESC LIMIT 1",
            guild_id,
        )
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to fetch lore session: {e}")
        return None
    finally:
        await _pool.release(conn)


async def save_studio_content(content_type: str, payload: str) -> None:
    """Store generated studio content for later publishing."""
    conn = await _get_connection()
    try:
        await conn.execute(
            "INSERT INTO studio_content (content_type, payload) VALUES ($1, $2)",
            content_type,
            payload,
        )
    except Exception as e:
        logger.error(f"Failed to save studio content: {e}")
    finally:
        await _pool.release(conn)


async def get_latest_studio_content(content_type: str) -> Optional[Dict[str, Any]]:
    """Get the latest stored studio content entry."""
    conn = await _get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM studio_content WHERE content_type = $1 ORDER BY created_at DESC LIMIT 1",
            content_type,
        )
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to fetch studio content: {e}")
        return None
    finally:
        await _pool.release(conn)


async def mark_studio_content_published(content_type: str) -> None:
    """Mark the latest studio content entry as published."""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE studio_content SET published_at = CURRENT_TIMESTAMP WHERE content_type = $1 AND published_at IS NULL ORDER BY created_at DESC LIMIT 1",
            content_type,
        )
    except Exception as e:
        logger.error(f"Failed to mark studio content as published: {e}")
    finally:
        await _pool.release(conn)


async def save_weekly_cast(
    week_of: datetime,
    members: str,
    anime_style: str,
    image_url: str,
) -> None:
    """Save weekly cast data to database."""
    conn = await _get_connection()
    try:
        await conn.execute("""
            INSERT INTO weekly_cast (week_of, members, anime_style, image_url)
            VALUES ($1, $2, $3, $4)
        """, week_of, members, anime_style, image_url)
    except Exception as e:
        logger.error(f"Failed to save weekly cast: {e}")
    finally:
        await _pool.release(conn)


async def get_users_by_screen_time_threshold(threshold: int) -> List[Dict[str, Any]]:
    """Get all users with screen time >= threshold."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch(
            "SELECT * FROM users WHERE screen_time >= $1 ORDER BY screen_time DESC",
            threshold
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get users by threshold: {e}")
        return []
    finally:
        await _pool.release(conn)


async def reset_user_screen_time(user_id: int) -> int:
    """Reset a user's screen time to zero."""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE users SET screen_time = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = $1",
            user_id,
        )
        return 0
    except Exception as e:
        logger.error(f"Failed to reset screen time for user {user_id}: {e}")
        return 0
    finally:
        await _pool.release(conn)


async def set_user_role(user_id: int, role_id: Optional[int]) -> None:
    """Update the current role for a user in the database."""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE users SET current_role_id = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2",
            role_id,
            user_id,
        )
    except Exception as e:
        logger.error(f"Failed to set role for user {user_id}: {e}")
    finally:
        await _pool.release(conn)


async def get_user_promotion_history(user_id: int) -> List[Dict[str, Any]]:
    """Get promotion history for a user."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch(
            "SELECT * FROM promotions WHERE user_id = $1 ORDER BY created_at ASC",
            user_id,
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get promotion history: {e}")
        return []
    finally:
        await _pool.release(conn)


async def get_weekly_cast_appearances(user_id: int) -> List[str]:
    """Get weekly cast appearance labels for a user."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch("SELECT members FROM weekly_cast")
        appearances = []
        for row in rows:
            members = row['members']
            if str(user_id) in members:
                appearances.append(str(row['week_of']))
        return appearances
    except Exception as e:
        logger.error(f"Failed to get weekly cast appearances: {e}")
        return []
    finally:
        await _pool.release(conn)


async def get_newspaper_features(user_id: int) -> List[str]:
    """Get newspaper feature labels for a user."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch("SELECT headline, summary FROM newspapers")
        features = []
        for row in rows:
            text = f"{row['headline']}"
            if str(user_id) in row['summary']:
                features.append(text)
        return features
    except Exception as e:
        logger.error(f"Failed to get newspaper features: {e}")
        return []
    finally:
        await _pool.release(conn)
