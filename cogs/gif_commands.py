from utils.cooldowns import get_remaining, set_cooldown
from discord.ext import commands

from utils.gif_api import fetch_gif
from utils.embeds import create_gif_embed


COMMANDS = {
    "rizz": "rizz",
    "larp": "larp",
    "jojos": "jojo anime",
    "blush": "anime blush",
    "ohio": "ohio meme",
    "cooked": "cooked meme",
    "fumble": "fumble meme",
    "isekai": "isekai anime",
    "stare": "anime stare",
    "cope": "cope meme",
    "based": "based meme",
    "skillissue": "skill issue meme",
    "touchgrass": "touch grass meme",
    "caught": "caught in 4k meme",
    "letmecook": "let him cook meme",
    "fraudwatch": "fraud watch meme",
    "canon": "canon event meme",
    "villainarc": "villain arc anime",
    "aura": "aura meme",
    "huh": "huh meme"
}


CAPTIONS = {
    "rizz": "has activated the rizz technique.",
    "larp": "has entered full roleplay mode.",
    "jojos": "has triggered dramatic anime energy.",
    "blush": "is feeling shy.",
    "ohio": "has entered the Ohio dimension.",
    "cooked": "is completely cooked.",
    "fumble": "has fumbled the moment.",
    "isekai": "has been transported somewhere random.",
    "stare": "is staring intensely.",
    "cope": "has entered the cope zone.",
    "based": "has delivered a based opinion.",
    "skillissue": "has suffered a skill issue.",
    "touchgrass": "has been ordered to touch grass.",
    "caught": "has been caught in 4K.",
    "letmecook": "has started cooking.",
    "fraudwatch": "is currently under fraud watch.",
    "canon": "has created a canon event.",
    "villainarc": "has started a villain arc.",
    "aura": "has gained aura.",
    "huh": "is confused."
}


class GifCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def run_action(ctx, command_name):
    mentions = ctx.message.mentions

    if len(mentions) > 4:
        await ctx.send(
            "❌ Maximum 4 users can be targeted."
        )
        return


    # Cooldown check
    remaining = get_remaining(ctx.author.id)

    if remaining > 0:
        await ctx.send(
            f"⏳ Post nut clarity is here. Try again in {remaining}s."
        )
        return


    # Determine cooldown length
    if len(mentions) >= 2:
        cooldown_time = 600  # 10 minutes

        roles = [
            role.name.lower()
            for role in ctx.author.roles
        ]

        if (
            "main character" in roles
            or "main cast" in roles
        ):
            cooldown_time = 120  # 2 minutes

    else:
        cooldown_time = 3


    set_cooldown(
        ctx.author.id,
        cooldown_time
    )


    if mentions:
        targets = " ".join(
            user.mention for user in mentions
        )
    else:
        targets = ctx.author.mention


    gif = await fetch_gif(
        COMMANDS[command_name]
    )

    if not gif:
        await ctx.send(
            "❌ No GIF found."
        )
        return


    embed = create_gif_embed(
        f"✨ {command_name.upper()} ✨",
        f"{targets} {CAPTIONS[command_name]}",
        gif
    )

    await ctx.send(embed=embed)


def create_command(command_name):

    async def command(ctx):
        await run_action(
            ctx,
            command_name
        )

    command.__name__ = command_name

    return commands.Command(
        command,
        name=command_name
    )


async def setup(bot):

    cog = GifCommands(bot)

    await bot.add_cog(cog)

    for command_name in COMMANDS:
        bot.add_command(
            create_command(command_name)
        )