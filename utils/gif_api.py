import aiohttp
import random

from config import KLIPY_URL, KLIPY_KEY


async def fetch_gif(query: str):
    params = {
        "q": query,
        "limit": 10,
        "key": KLIPY_KEY
    }

    try:
        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                KLIPY_URL,
                params=params,
                timeout=timeout
            ) as response:

                if response.status != 200:
                    return None

                payload = await response.json()

    except Exception:
        return None


    gifs = []

    for item in payload.get("results", []):
        try:
            url = item["media_formats"]["gif"]["url"]

            if url:
                gifs.append(url)

        except Exception:
            pass


    if not gifs:
        return None


    return random.choice(gifs)