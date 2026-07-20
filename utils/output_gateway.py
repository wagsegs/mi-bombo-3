import logging
from enum import Enum
from typing import Optional, Any

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    COMMAND_RESPONSE = "COMMAND_RESPONSE"
    WELCOME = "WELCOME"
    DIRECTOR_NOTES = "DIRECTOR_NOTES"
    PROMOTION = "PROMOTION"
    NEWSPAPER = "NEWSPAPER"
    WEEKLY_CAST = "WEEKLY_CAST"
    LORE = "LORE"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"


APPROVED_MESSAGE_TYPES = {
    MessageType.COMMAND_RESPONSE,
    MessageType.WELCOME,
    MessageType.DIRECTOR_NOTES,
    MessageType.PROMOTION,
    MessageType.NEWSPAPER,
    MessageType.WEEKLY_CAST,
    MessageType.LORE,
    MessageType.SYSTEM_NOTIFICATION,
}


async def send_output(
    destination: Any,
    content: Optional[str] = None,
    *,
    message_type: MessageType | str,
    module: str = "unknown",
    reply: bool = False,
    channel: Any = None,
    **kwargs: Any,
) -> Any:
    """Send a Discord message only through the approved Studio output gateway."""
    normalized_type = _normalize_message_type(message_type)
    if normalized_type is None or normalized_type not in APPROVED_MESSAGE_TYPES:
        logger.warning(
            "Blocked outgoing message\nReason: Unknown message type\nModule: %s\nChannel: %s",
            module,
            getattr(channel or destination, "id", None),
        )
        return None

    try:
        if destination is None:
            logger.warning("Blocked outgoing message\nReason: No destination\nModule: %s", module)
            return None

        if not hasattr(destination, "send") and channel is not None and hasattr(channel, "send"):
            destination = channel

        method = destination.reply if reply and hasattr(destination, "reply") else destination.send
        return await method(content=content, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive hardening
        logger.exception("Failed to send approved output via gateway: %s", exc)
        return None


def _normalize_message_type(message_type: MessageType | str | None) -> Optional[MessageType]:
    if message_type is None:
        return None
    if isinstance(message_type, MessageType):
        return message_type
    try:
        return MessageType(str(message_type).upper())
    except ValueError:
        return None
