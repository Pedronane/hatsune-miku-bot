import json
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
CONFIG = Path(__file__).parent / "config.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {}


def save_config(data):
    CONFIG.write_text(json.dumps(data, indent=2))


STRUCTURE = {
    "📌 INFO": [
        ("text", "📜-regole", "regole"),
        ("text", "📢-annunci", "annunci"),
        ("text", "🎭-ruoli", "ruoli"),
    ],
    "💬 GENERALE": [
        ("text", "💬-chat", "chat"),
        ("text", "📸-media", "media"),
        ("text", "😂-meme", "meme"),
        ("text", "🔗-link", "link"),
    ],
    "🎮 ROBA": [
        ("text", "🕹️-gaming", "gaming"),
        ("text", "🎵-musica", "musica"),
        ("text", "🎲-off-topic", "off-topic"),
    ],
    "🔊 VOCALI": [
        ("voice", "🔊 General", "voc-general"),
        ("voice", "🎮 Gaming", "voc-gaming"),
        ("voice", "💤 AFK", "afk"),
    ],
    "🛠️ STAFF": [
        ("text", "📋-log", "log"),
        ("text", "🔧-mod-chat", "mod-chat"),
    ],
}

ROLES = [
    ("🛡️ Mod", discord.Colour.red(), True),
    ("🎮 Gamer", discord.Colour.blue(), False),
    ("🎵 Music", discord.Colour.purple(), False),
    ("🎨 Creative", discord.Colour.orange(), False),
]

REACTION_ROLES = {
    "🎮": "🎮 Gamer",
    "🎵": "🎵 Music",
    "🎨": "🎨 Creative",
}


@bot.event
async def on_ready():
    print(f"Online come {bot.user} — {len(bot.guilds)} server")


ROLE_PACK = [
    ("👑 Boss", 0xF1C40F),
    ("🎮 Gamer", 0x2ECC71),
    ("🎵 DJ", 0xE74C3C),
    ("⚽ Sportivo", 0x27AE60),
    ("💻 Smanettone", 0x3498DB),
    ("🎬 Cinefilo", 0x8E44AD),
    ("😎 Veterano", 0xE67E22),
    ("🎲 Game Night", 0x57F287),
]


@bot.command()
@commands.has_permissions(administrator=True)
async def makeroles(ctx):
    guild = ctx.guild
    await ctx.send(f"🎨 Creo {len(ROLE_PACK)} ruoli...")
    count = 0
    for name, colour in ROLE_PACK:
        if discord.utils.get(guild.roles, name=name):
            continue
        hoist = name.startswith("—")
        await guild.create_role(name=name, colour=discord.Colour(colour), hoist=hoist, mentionable=True)
        count += 1
    await ctx.send(f"✅ {count} ruoli creati. I `— ... —` sono separatori visivi.")


@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx, channel: discord.TextChannel, *, text):
    await channel.send(text)
    await ctx.message.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def embed(ctx, channel: discord.TextChannel, title, *, text):
    e = discord.Embed(title=title, description=text, colour=discord.Colour.blurple())
    await channel.send(embed=e)
    await ctx.message.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx):
    guild = ctx.guild
    data = {
        "guild": guild.name,
        "roles": [
            {
                "name": r.name,
                "colour": r.colour.value,
                "hoist": r.hoist,
                "mentionable": r.mentionable,
                "permissions": r.permissions.value,
                "position": r.position,
            }
            for r in guild.roles
            if not r.is_default()
        ],
        "categories": [
            {
                "name": c.name,
                "channels": [
                    {"name": ch.name, "type": str(ch.type), "position": ch.position}
                    for ch in c.channels
                ],
            }
            for c in guild.categories
        ],
        "uncategorized": [
            {"name": ch.name, "type": str(ch.type)}
            for ch in guild.channels
            if ch.category is None and not isinstance(ch, discord.CategoryChannel)
        ],
    }
    path = Path(__file__).parent / f"backup_{guild.id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    await ctx.send("💾 Backup struttura salvato.", file=discord.File(path))


@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx, confirm: str = ""):
    if confirm != "confirm":
        await ctx.send(
            "⚠️ **Distruzione totale e irreversibile.** Cancella TUTTI i canali e ruoli.\n"
            "Fai prima `!backup`. Per procedere: `!nuke confirm`"
        )
        return
    guild = ctx.guild
    me = guild.me
    for channel in list(guild.channels):
        if channel == ctx.channel:
            continue
        await channel.delete()
    for role in list(guild.roles):
        if role.is_default() or role.managed or role >= me.top_role:
            continue
        await role.delete()
    await ctx.send("💥 Server azzerato. Lancia `!setup` per ricostruire.")


@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    guild = ctx.guild
    await ctx.send("⚙️ Costruisco il server...")

    created_roles = {}
    for name, colour, hoist in ROLES:
        existing = discord.utils.get(guild.roles, name=name)
        role = existing or await guild.create_role(name=name, colour=colour, hoist=hoist, mentionable=True)
        created_roles[name] = role

    staff_role = created_roles["🛡️ Mod"]
    made = {}
    for cat_name, channels in STRUCTURE.items():
        overwrites = {}
        if cat_name == "🛠️ STAFF":
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                staff_role: discord.PermissionOverwrite(view_channel=True),
            }
        category = await guild.create_category(cat_name, overwrites=overwrites)
        for ch_type, ch_name, key in channels:
            if ch_type == "text":
                made[key] = await guild.create_text_channel(ch_name, category=category)
            else:
                made[key] = await guild.create_voice_channel(ch_name, category=category)

    await guild.edit(afk_channel=made["afk"], afk_timeout=300)

    ruoli_ch = made["ruoli"]
    embed = discord.Embed(
        title="🎭 Scegli i tuoi ruoli",
        description="Reagisci per assegnarti un ruolo:\n\n"
        + "\n".join(f"{e} → **{r}**" for e, r in REACTION_ROLES.items()),
        colour=discord.Colour.blurple(),
    )
    msg = await ruoli_ch.send(embed=embed)
    for emoji in REACTION_ROLES:
        await msg.add_reaction(emoji)

    config = load_config()
    config["reaction_message_id"] = msg.id
    config["reaction_map"] = {e: created_roles[r].id for e, r in REACTION_ROLES.items()}
    config["welcome_channel_id"] = made["chat"].id
    save_config(config)

    await ctx.send("✅ Fatto. Reaction roles attivi in #ruoli.")


@bot.event
async def on_raw_reaction_add(payload):
    await handle_reaction(payload, add=True)


@bot.event
async def on_raw_reaction_remove(payload):
    await handle_reaction(payload, add=False)


async def handle_reaction(payload, add):
    config = load_config()
    if payload.message_id != config.get("reaction_message_id"):
        return
    role_id = config.get("reaction_map", {}).get(str(payload.emoji))
    if role_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(role_id)
    member = guild.get_member(payload.user_id)
    if member is None or member.bot:
        return
    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


@bot.event
async def on_member_join(member):
    config = load_config()
    ch = member.guild.get_channel(config.get("welcome_channel_id", 0))
    if ch is None:
        return
    embed = discord.Embed(
        title="👋 Benvenuto!",
        description=f"Ehi {member.mention}, benvenuto su **{member.guild.name}**!\n"
        "Passa da <#ruoli> per i tuoi ruoli. 🎉",
        colour=discord.Colour.green(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    await ch.send(embed=embed)


bot.run(TOKEN)
