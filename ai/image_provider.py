import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


async def generate_image(prompt: str) -> Optional[str]:
    """Generate an image with Pollinations and save it to a temporary file."""
    provider = os.getenv("IMAGE_PROVIDER", "pollinations").lower()
    if provider != "pollinations":
        logger.warning("Unsupported image provider %s; expected Pollinations", provider)
        return None

    base_url = os.getenv("POLLINATIONS_IMAGE_BASE_URL") or os.getenv("POLLINATIONS_BASE_URL")
    if not base_url:
        logger.error("Missing Pollinations image endpoint configuration")
        return None

    if not prompt:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{base_url.rstrip('/')}/prompt/{prompt}"
            async with session.get(url, timeout=60) as response:
                response.raise_for_status()
                suffix = ".png"
                if response.content_type and "jpeg" in response.content_type.lower():
                    suffix = ".jpg"
                elif response.content_type and "webp" in response.content_type.lower():
                    suffix = ".webp"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    while True:
                        chunk = await response.content.read(1024 * 64)
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                    tmp_path = Path(tmp_file.name)
                return str(tmp_path)
    except Exception as exc:
        logger.error("Pollinations image generation failed: %s", exc)
        return None


def cleanup_temp_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        logger.debug("Failed to remove temporary image file %s", path)
