import asyncio
import random
import time
from collections import defaultdict

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

STREAM_TTL = 1800  # i link diretti YouTube scadono: ri-risolvi se più vecchi di 30 min

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


def fmt_dur(seconds):
    if not seconds:
        return "?:??"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class Track:
    def __init__(self, info, requester):
        self.title = info["title"]
        self.url = info["url"]
        self.webpage = info.get("webpage_url", "")
        self.duration = info.get("duration")
        self.requester = requester
        self.fetched = time.monotonic()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = defaultdict(list)
        self.current = {}
        self.loop_modes = defaultdict(lambda: "off")
        self.volumes = defaultdict(lambda: 1.0)

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

    async def connect_member(self, member):
        if not member.voice:
            return None
        channel = member.voice.channel
        vc = member.guild.voice_client
        if vc is None:
            return await channel.connect()
        if vc.channel != channel:
            await vc.move_to(channel)
        return vc

    async def _extract(self, query):
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        if "entries" in data:
            data = data["entries"][0]
        return data

    async def enqueue(self, member, query):
        guild = member.guild
        track = Track(await self._extract(query), member)
        self.queues[guild.id].append(track)
        vc = guild.voice_client
        started = not (vc.is_playing() or vc.is_paused())
        if started:
            self.play_next(guild)
        return track, started

    async def _stream_url(self, track):
        if track.url and (time.monotonic() - track.fetched) < STREAM_TTL:
            return track.url
        data = await self._extract(track.webpage or track.title)
        track.url = data["url"]
        track.fetched = time.monotonic()
        return track.url

    def play_next(self, guild):
        asyncio.run_coroutine_threadsafe(self._advance(guild), self.bot.loop)

    async def _advance(self, guild):
        vc = guild.voice_client
        if vc is None:
            return
        gid = guild.id
        mode = self.loop_modes[gid]
        prev = self.current.get(gid)
        queue = self.queues[gid]
        if mode == "one" and prev:
            track = prev
        else:
            if mode == "all" and prev:
                queue.append(prev)
            if not queue:
                self.current[gid] = None
                return
            track = queue.pop(0)
        self.current[gid] = track
        try:
            url = await self._stream_url(track)
        except Exception:
            self.play_next(guild)  # brano morto/non risolvibile: passa al prossimo
            return
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(url, **FFMPEG_OPTS), volume=self.volumes[gid]
        )
        vc.play(source, after=lambda e: self.play_next(guild))

    @app_commands.command(description="Metti su una canzone (nome o link YouTube)")
    async def play(self, interaction: discord.Interaction, brano: str):
        vc = await self.ensure_voice(interaction)
        if vc is None:
            return
        await interaction.response.defer()
        try:
            data = await self._extract(brano)
        except Exception as e:
            await interaction.followup.send(f"❌ Non riesco a prendere il brano: `{str(e)[:150]}`")
            return
        track = Track(data, interaction.user)
        self.queues[interaction.guild_id].append(track)
        if vc.is_playing() or vc.is_paused():
            pos = len(self.queues[interaction.guild_id])
            await interaction.followup.send(f"➕ In coda (#{pos}): **{track.title}** `{fmt_dur(track.duration)}`")
        else:
            self.play_next(interaction.guild)
            await interaction.followup.send(f"🎵 Ora suona: **{track.title}** `{fmt_dur(track.duration)}`")

    @app_commands.command(description="Salta il brano corrente")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skippato.")
        else:
            await interaction.response.send_message("Non sta suonando niente.", ephemeral=True)

    @app_commands.command(description="Pausa il brano")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Pausa.")
        else:
            await interaction.response.send_message("Non sta suonando niente.", ephemeral=True)

    @app_commands.command(description="Riprende il brano")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Riprende.")
        else:
            await interaction.response.send_message("Niente in pausa.", ephemeral=True)

    @app_commands.command(description="Ferma tutto e svuota la coda")
    async def stop(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        self.queues[gid].clear()
        self.loop_modes[gid] = "off"
        self.current[gid] = None
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
        await interaction.response.send_message("⏹️ Stop. Coda svuotata.")

    @app_commands.command(description="Mostra la coda")
    async def queue(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        q = self.queues[gid]
        cur = self.current.get(gid)
        if not cur and not q:
            await interaction.response.send_message("Coda vuota.")
            return
        embed = discord.Embed(title="🎶 Coda", colour=discord.Colour.blurple())
        if cur:
            embed.add_field(
                name="▶️ Ora suona",
                value=f"**{cur.title}** `{fmt_dur(cur.duration)}` — {cur.requester.mention}",
                inline=False,
            )
        if q:
            lines = [f"`{i + 1}.` {t.title} `{fmt_dur(t.duration)}`" for i, t in enumerate(q[:10])]
            if len(q) > 10:
                lines.append(f"…e altri {len(q) - 10}")
            tot = sum(t.duration or 0 for t in q)
            embed.add_field(name=f"In coda ({len(q)}) — {fmt_dur(tot)}", value="\n".join(lines), inline=False)
        loop_label = {"off": "off", "one": "🔂 brano", "all": "🔁 coda"}[self.loop_modes[gid]]
        embed.set_footer(text=f"Loop: {loop_label} · Volume: {int(self.volumes[gid] * 100)}%")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Brano in riproduzione")
    async def np(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        cur = self.current.get(gid)
        vc = interaction.guild.voice_client
        if not cur or not vc or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message("Non sta suonando niente.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎵 Ora suona",
            description=f"**[{cur.title}]({cur.webpage})**" if cur.webpage else f"**{cur.title}**",
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Durata", value=fmt_dur(cur.duration))
        embed.add_field(name="Richiesto da", value=cur.requester.mention)
        loop_label = {"off": "off", "one": "🔂 brano", "all": "🔁 coda"}[self.loop_modes[gid]]
        embed.set_footer(text=f"Loop: {loop_label} · Volume: {int(self.volumes[gid] * 100)}%")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Mescola la coda")
    async def shuffle(self, interaction: discord.Interaction):
        q = self.queues[interaction.guild_id]
        if len(q) < 2:
            await interaction.response.send_message("Niente da mescolare.", ephemeral=True)
            return
        random.shuffle(q)
        await interaction.response.send_message(f"🔀 Coda mescolata ({len(q)} brani).")

    @app_commands.command(description="Ripeti: off / brano / coda")
    @app_commands.choices(modo=[
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="brano", value="one"),
        app_commands.Choice(name="coda", value="all"),
    ])
    async def loop(self, interaction: discord.Interaction, modo: app_commands.Choice[str]):
        self.loop_modes[interaction.guild_id] = modo.value
        labels = {"off": "❌ Loop off", "one": "🔂 Ripeto il brano", "all": "🔁 Ripeto la coda"}
        await interaction.response.send_message(labels[modo.value])

    @app_commands.command(description="Volume 0-200%")
    async def volume(self, interaction: discord.Interaction, livello: app_commands.Range[int, 0, 200]):
        gid = interaction.guild_id
        self.volumes[gid] = livello / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = livello / 100
        await interaction.response.send_message(f"🔊 Volume: {livello}%")

    @app_commands.command(description="Togli un brano dalla coda per posizione")
    async def remove(self, interaction: discord.Interaction, posizione: app_commands.Range[int, 1]):
        q = self.queues[interaction.guild_id]
        if posizione > len(q):
            await interaction.response.send_message("Posizione fuori range.", ephemeral=True)
            return
        t = q.pop(posizione - 1)
        await interaction.response.send_message(f"🗑️ Tolto: **{t.title}**")

    @app_commands.command(description="Svuota la coda (continua il brano corrente)")
    async def clear(self, interaction: discord.Interaction):
        n = len(self.queues[interaction.guild_id])
        self.queues[interaction.guild_id].clear()
        await interaction.response.send_message(f"🧹 Coda svuotata ({n} brani).")

    @app_commands.command(description="Caccia il bot dal vocale")
    async def leave(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        vc = interaction.guild.voice_client
        if vc:
            self.queues[gid].clear()
            self.loop_modes[gid] = "off"
            self.current[gid] = None
            await vc.disconnect()
            await interaction.response.send_message("👋 Tolto il disturbo.")
        else:
            await interaction.response.send_message("Non sono in nessun vocale.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Music(bot))
