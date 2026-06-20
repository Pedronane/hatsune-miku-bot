import re
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import db

# Compila con le parole da bloccare (minuscolo). Vuoto = filtro parolacce disattivo.
BADWORDS = set()
INVITE = re.compile(r"(discord\.gg/|discord\.com/invite/)", re.I)
SPAM_WINDOW = 7
SPAM_MAX = 5
RAID_WINDOW = 10
RAID_MAX = 5


def parse_duration(s):
    m = re.fullmatch(r"(\d+)([smhd])", s.lower())
    if not m:
        return None
    n = int(m.group(1))
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recent = defaultdict(lambda: deque(maxlen=SPAM_MAX))
        self.joins = deque()

    def log_channel(self, guild):
        return discord.utils.find(lambda c: "log" in c.name, guild.text_channels)

    async def log(self, guild, embed):
        ch = self.log_channel(guild)
        if ch:
            await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return
        content = message.content.lower()
        words = set(re.findall(r"\w+", content))
        reason = None
        if words & BADWORDS:
            reason = "linguaggio vietato"
        elif INVITE.search(content):
            reason = "invite link"
        else:
            dq = self.recent[(message.guild.id, message.author.id)]
            dq.append(time.time())
            if len(dq) == SPAM_MAX and dq[-1] - dq[0] < SPAM_WINDOW:
                reason = "spam"
                dq.clear()
        if reason:
            await message.delete()
            embed = discord.Embed(
                title="🛡️ Automod",
                description=f"Cancellato messaggio di {message.author.mention} — **{reason}**",
                colour=discord.Colour.orange(),
            )
            await self.log(message.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        now = time.time()
        self.joins.append(now)
        while self.joins and now - self.joins[0] > RAID_WINDOW:
            self.joins.popleft()
        if len(self.joins) >= RAID_MAX:
            embed = discord.Embed(
                title="🚨 Possibile raid",
                description=f"{len(self.joins)} ingressi in {RAID_WINDOW}s. Controllate.",
                colour=discord.Colour.red(),
            )
            await self.log(member.guild, embed)

    @app_commands.command(description="Caccia uno a calci")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "nessuno"):
        try:
            await membro.kick(reason=motivo)
        except discord.HTTPException:
            await interaction.response.send_message("Non ce la faccio: ruolo troppo alto o permessi mancanti.", ephemeral=True)
            return
        await interaction.response.send_message(f"👢 {membro} kickato. Motivo: {motivo}")
        await self.log(interaction.guild, discord.Embed(
            title="👢 Kick", description=f"{membro.mention} da {interaction.user.mention}\nMotivo: {motivo}",
            colour=discord.Colour.orange()))

    @app_commands.command(description="Banna uno per sempre")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "nessuno"):
        try:
            await membro.ban(reason=motivo)
        except discord.HTTPException:
            await interaction.response.send_message("Non ce la faccio: ruolo troppo alto o permessi mancanti.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔨 {membro} bannato. Motivo: {motivo}")
        await self.log(interaction.guild, discord.Embed(
            title="🔨 Ban", description=f"{membro.mention} da {interaction.user.mention}\nMotivo: {motivo}",
            colour=discord.Colour.red()))

    @app_commands.command(description="Sbanna uno (ID utente)")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not user_id.isdigit():
            await interaction.response.send_message("Serve un ID utente numerico.", ephemeral=True)
            return
        try:
            await interaction.guild.unban(discord.Object(id=int(user_id)))
        except discord.NotFound:
            await interaction.response.send_message("Quell'utente non è bannato.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("Non riesco a sbannare: permessi mancanti.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Sbannato `{user_id}`.")

    @app_commands.command(description="Mute temporaneo, es: 10m 1h")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, membro: discord.Member, durata: str, motivo: str = "nessuno"):
        secs = parse_duration(durata)
        if secs is None or secs > 2419200:
            await interaction.response.send_message("Durata tipo `10m`, `2h`, `1d` (max 28d).", ephemeral=True)
            return
        try:
            await membro.timeout(timedelta(seconds=secs), reason=motivo)
        except discord.HTTPException:
            await interaction.response.send_message("Non ce la faccio: ruolo troppo alto o permessi mancanti.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔇 {membro.mention} mutato per {durata}. Motivo: {motivo}")
        await self.log(interaction.guild, discord.Embed(
            title="🔇 Mute", description=f"{membro.mention} per {durata} da {interaction.user.mention}\nMotivo: {motivo}",
            colour=discord.Colour.orange()))

    @app_commands.command(description="Togli il mute")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            await membro.timeout(None)
        except discord.HTTPException:
            await interaction.response.send_message("Non riesco a smutare: permessi mancanti.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔊 {membro.mention} smutato.")

    @app_commands.command(description="Ammonisci uno")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        db.add_warn(interaction.guild_id, membro.id, interaction.user.id, motivo)
        n = len(db.get_warns(interaction.guild_id, membro.id))
        await interaction.response.send_message(f"⚠️ {membro.mention} ammonito ({n}° warn). Motivo: {motivo}")
        await self.log(interaction.guild, discord.Embed(
            title="⚠️ Warn", description=f"{membro.mention} ({n} totali) da {interaction.user.mention}\nMotivo: {motivo}",
            colour=discord.Colour.yellow()))

    @app_commands.command(description="Vedi i warn di uno")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, membro: discord.Member):
        rows = db.get_warns(interaction.guild_id, membro.id)
        if not rows:
            await interaction.response.send_message(f"{membro.mention} è pulito.")
            return
        lines = [f"<t:{r['ts']}:R> — {r['reason']} (da <@{r['mod_id']}>)" for r in rows]
        embed = discord.Embed(title=f"⚠️ Warn di {membro.display_name}",
                              description="\n".join(lines), colour=discord.Colour.yellow())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Cancella N messaggi dal canale")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, quantita: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=quantita)
        await interaction.followup.send(f"🧹 Cancellati {len(deleted)} messaggi.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Mod(bot))
