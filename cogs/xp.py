import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db

COOLDOWN = 60


class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        key = (message.guild.id, message.author.id)
        now = time.time()
        if now - self.last.get(key, 0) < COOLDOWN:
            return
        self.last[key] = now
        db.add_xp(message.guild.id, message.author.id, random.randint(15, 25))

    @app_commands.command(description="Mostra i tuoi punti, sei nessuno o sei qualcuno?")
    async def rank(self, interaction: discord.Interaction):
        xp = db.get_xp(interaction.guild_id, interaction.user.id)
        level = int((xp / 100) ** 0.5)
        await interaction.response.send_message(
            f"🪪 {interaction.user.mention} — **{xp} XP**, livello **{level}**."
        )

    @app_commands.command(description="La classifica dei più sboroni del server")
    async def top(self, interaction: discord.Interaction):
        rows = db.top_xp(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("Nessuno ha scritto un cazzo. Classifica vuota.")
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — {row['xp']} XP")
        embed = discord.Embed(
            title="🏆 Classifica XP", description="\n".join(lines), colour=discord.Colour.gold()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(XP(bot))
