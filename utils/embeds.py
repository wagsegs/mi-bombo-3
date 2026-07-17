import random
import discord


COLORS = [
    0xff9ff3,
    0x54a0ff,
    0x5f27cd,
    0x1dd1a1,
    0xff6b6b,
    0xfeca57,
]


def create_gif_embed(title, description, gif_url):
    embed = discord.Embed(
        title=title,
        description=description,
        color=random.choice(COLORS)
    )

    embed.set_image(url=gif_url)

    embed.set_footer(
        text="MI BOM3O"
    )

    return embed