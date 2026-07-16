import discord

from utils.cooldowns import get_remaining, set_cooldown
from discord.ext import commands

from config import PREFIX
from utils.gif_api import fetch_gif
from utils.embeds import create_gif_embed


def extract_custom_query(content, prefix="."):
    if not content:
        return None

    stripped = content.strip()

    if not stripped.startswith(prefix):
        return None

    without_prefix = stripped[len(prefix):].strip()

    if not without_prefix:
        return None

    if not without_prefix.startswith("c"):
        return None

    query = without_prefix[1:].strip()

    return query or None


def build_custom_gif_details(ctx, prefix="."):
    original_content = getattr(ctx.message, "content", "") or ""
    mentions = list(getattr(ctx.message, "mentions", []) or [])

    query = extract_custom_query(original_content, prefix)

    if not query:
        return None, None

    cleaned_query = query

    for mention in mentions:
        mention_text = getattr(mention, "mention", None)

        if mention_text:
            cleaned_query = cleaned_query.replace(mention_text, " ")

    cleaned_query = " ".join(cleaned_query.split())

    if not cleaned_query:
        return None, None

    targets = " ".join(
        getattr(mention, "mention", "") for mention in mentions if getattr(mention, "mention", None)
    )

    if targets:
        target_label = "Target:" if len(mentions) == 1 else "Targets:"
        target_section = f"{target_label}\n{targets}"
    else:
        target_section = None

    description_parts = [f"Requested by {ctx.author.mention}"]

    if target_section:
        description_parts.append("")
        description_parts.append(target_section)

    description_parts.extend(["", "Query:", f"`{cleaned_query}`"])

    return cleaned_query, "\n".join(description_parts)


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

HELP_DESCRIPTIONS = {
    "rizz": "Sends a rizz-style reaction",
    "larp": "Triggers full roleplay energy",
    "jojos": "Brings dramatic anime vibes",
    "blush": "Shows a shy anime moment",
    "ohio": "Plays the Ohio meme energy",
    "cooked": "Sends a cooked meme reaction",
    "fumble": "Shows a classic fumble moment",
    "isekai": "Starts an isekai-style scene",
    "stare": "Adds a strong anime stare",
    "cope": "Shows a coping meme",
    "based": "Drops a based reaction",
    "skillissue": "Calls out a skill issue",
    "touchgrass": "Orders someone to touch grass",
    "caught": "Catches someone in 4K",
    "letmecook": "Lets the cooking meme begin",
    "fraudwatch": "Puts someone under fraud watch",
    "canon": "Creates a canon event moment",
    "villainarc": "Starts a villain arc",
    "aura": "Adds a powerful aura vibe",
    "huh": "Sends a confused reaction"
}


class GifCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def _apply_cooldown(ctx, cooldown_time=None):
    remaining = get_remaining(ctx.author.id)

    if remaining > 0:
        await ctx.send(
            f"⏳ Post nut clarity is here. Try again in {remaining}s."
        )
        return False

    if cooldown_time is None:
        mentions = ctx.message.mentions

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

    set_cooldown(ctx.author.id, cooldown_time)
    return True


async def run_action(ctx, command_name):
    mentions = ctx.message.mentions

    if len(mentions) > 4:
        await ctx.send(
            "❌ Maximum 4 users can be targeted."
        )
        return

    if not await _apply_cooldown(ctx):
        return

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


async def run_custom_action(ctx):
    mentions = ctx.message.mentions

    if len(mentions) > 4:
        await ctx.send(
            "❌ Maximum 4 users can be targeted."
        )
        return

    query, description = build_custom_gif_details(ctx, PREFIX)

    if not query or not description:
        await ctx.send(
            "Please provide something to search for.\n\nExample:\n.c door shutting"
        )
        return

    if not await _apply_cooldown(ctx, 3):
        return

    gif = await fetch_gif(query)

    if not gif:
        await ctx.send(
            f"Couldn't find any GIFs for:\n{query}"
        )
        return

    embed = create_gif_embed(
        "🎬 Custom GIF",
        description,
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


def create_custom_command():

    async def custom_command(ctx, *args):
        query = " ".join(args)

        if not query:
            await ctx.send(
                "Please provide something to search for.\n\nExample:\n.c door shutting"
            )
            return

        await run_custom_action(ctx)

    custom_command.__name__ = "c"

    return commands.Command(
        custom_command,
        name="c"
    )


def create_help_command():

    async def help_command(ctx):
        embed = discord.Embed(
            title="bomboclat commands",
            description="Use these commands in chat.",
            color=0x9b5de5
        )
        embed.set_footer(text=f"Prefix: {PREFIX}")

        for command_name in COMMANDS:
            description = HELP_DESCRIPTIONS.get(command_name, "Funny reaction command")
            embed.add_field(
                name=f"`{PREFIX}{command_name}`",
                value=description,
                inline=True
            )

        embed.add_field(
            name=f"`{PREFIX}c`",
            value="Searches Klipy for any GIF you want",
            inline=True
        )

        await ctx.send(embed=embed)

    help_command.__name__ = "commands"

    return commands.Command(
        help_command,
        name="commands"
    )


async def setup(bot):

    cog = GifCommands(bot)

    await bot.add_cog(cog)

    bot.remove_command("help")
    bot.add_command(create_help_command())
    bot.add_command(create_custom_command())

    for command_name in COMMANDS:
        bot.add_command(
            create_command(command_name)
        )