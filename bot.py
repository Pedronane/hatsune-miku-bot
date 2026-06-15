import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import db

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]

COGS = ["cogs.music", "cogs.xp", "cogs.mod", "cogs.fun", "cogs.miku"]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.synced = False

    async def setup_hook(self):
        db.init()
        for ext in COGS:
            await self.load_extension(ext)

    async def on_ready(self):
        if not self.synced:
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            self.synced = True
        print(f"Online come {self.user} — {len(self.guilds)} server")


Bot().run(TOKEN)
