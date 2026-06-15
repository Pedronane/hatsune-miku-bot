import asyncio
from collections import defaultdict

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class Track:
    def __init__(self, info, requester):
        self.title = info["title"]
        self.url = info["url"]
        self.webpage = info.get("webpage_url", "")
        self.requester = requester


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = defaultdict(list)

    async def ensure_voice(self, interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Entra prima in un vocale, genio.", ephemeral=True)
            return None
        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client
        if vc is None:
            return await channel.connect()
        if vc.channel != channel:
            await vc.move_to(channel)
        return vc

    def play_next(self, guild):
        vc = guild.voice_client
        if vc is None:
            return
        queue = self.queues[guild.id]
        if not queue:
            return
        track = queue.pop(0)
        source = discord.FFmpegOpusAudio(track.url, **FFMPEG_OPTS)
        vc.play(source, after=lambda e: self.play_next(guild))

    @app_commands.command(description="Metti su una canzone (nome o link YouTube)")
    async def play(self, interaction: discord.Interaction, brano: str):
        vc = await self.ensure_voice(interaction)
        if vc is None:
            return
        await interaction.response.defer()
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(brano, download=False))
        if "entries" in data:
            data = data["entries"][0]
        track = Track(data, interaction.user)
        self.queues[interaction.guild_id].append(track)
        if vc.is_playing() or vc.is_paused():
            await interaction.followup.send(f"➕ In coda: **{track.title}**")
        else:
            self.play_next(interaction.guild)
            await interaction.followup.send(f"🎵 Ora suona: **{track.title}**")

    @app_commands.command(description="Salta il brano corrente")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skippato.")
        else:
            await interaction.response.send_message("Non sta suonando niente.", ephemeral=True)

    @app_commands.command(description="Ferma tutto e svuota la coda")
    async def stop(self, interaction: discord.Interaction):
        self.queues[interaction.guild_id].clear()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
        await interaction.response.send_message("⏹️ Stop. Coda svuotata.")

    @app_commands.command(description="Mostra la coda")
    async def queue(self, interaction: discord.Interaction):
        q = self.queues[interaction.guild_id]
        if not q:
            await interaction.response.send_message("Coda vuota.")
            return
        lines = [f"`{i + 1}.` {t.title}" for i, t in enumerate(q[:10])]
        embed = discord.Embed(title="🎶 Coda", description="\n".join(lines), colour=discord.Colour.blurple())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Caccia il bot dal vocale")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.queues[interaction.guild_id].clear()
            await vc.disconnect()
            await interaction.response.send_message("👋 Tolto il disturbo.")
        else:
            await interaction.response.send_message("Non sono in nessun vocale.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Music(bot))
