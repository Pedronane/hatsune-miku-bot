import asyncio
import json
import os

import discord
from discord import app_commands
from discord.ext import commands

PERSONA = (
    "Sei Hatsune Miku, controlli un bot dentro Minecraft per un gruppo di amici. "
    "Strumenti: goto (vai a coordinate x y z), come (raggiungi un giocatore), "
    "follow (segui un giocatore), stop (fermati), say (parla in chat). "
    "Se ti chiedono un'azione nel gioco usa SEMPRE lo strumento giusto. "
    "I nomi dei giocatori sono username esatti. Se dicono 'vieni da me', 'seguimi' o "
    "'raggiungimi' senza un nome, usa chi sta parlando. "
    "Parli italiano, frasi corte e ironiche."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "say", "description": "Scrivi un messaggio nella chat di Minecraft",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "goto", "description": "Vai a delle coordinate",
        "parameters": {"type": "object", "properties": {
            "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
            "required": ["x", "y", "z"]}}},
    {"type": "function", "function": {
        "name": "come", "description": "Raggiungi un giocatore una volta",
        "parameters": {"type": "object", "properties": {"player": {"type": "string"}}, "required": ["player"]}}},
    {"type": "function", "function": {
        "name": "follow", "description": "Segui un giocatore in continuazione",
        "parameters": {"type": "object", "properties": {"player": {"type": "string"}}, "required": ["player"]}}},
    {"type": "function", "function": {
        "name": "stop", "description": "Fermati, smetti di muoverti",
        "parameters": {"type": "object", "properties": {}}}},
]


class Minecraft(commands.Cog):
    mc = app_commands.Group(name="mc", description="Controlla il bot dentro Minecraft")

    def __init__(self, bot):
        self.bot = bot
        self.host = os.environ.get("MC_HOST", "localhost")
        self.port = int(os.environ.get("MC_PORT", "25565"))
        self.username = os.environ.get("MC_USERNAME", "Miku")
        self.version = os.environ.get("MC_VERSION") or False
        self.relay_id = int(os.environ.get("MC_RELAY_CHANNEL_ID", "0"))
        self.lib = None
        self.pf = None
        self.world = None
        self.movements = None
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            from groq import AsyncGroq
            self.groq = AsyncGroq(api_key=groq_key)
        else:
            self.groq = None

    def _push(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    async def _relay(self, text):
        if self.relay_id:
            ch = self.bot.get_channel(self.relay_id)
            if ch:
                await ch.send(text)

    def _require(self):
        if self.lib is None:
            from javascript import require
            self.lib = require("mineflayer")
            self.pf = require("mineflayer-pathfinder")

    def _connect(self):
        from javascript import On
        self._require()
        self.world = self.lib.createBot({
            "host": self.host, "port": self.port,
            "username": self.username, "auth": "offline", "version": self.version,
        })
        self.world.loadPlugin(self.pf.pathfinder)

        @On(self.world, "spawn")
        def _spawn(this):
            self.movements = self.pf.Movements(self.world)
            self._push(self._relay(f"🟢 **{self.username}** spawnato in Minecraft"))

        @On(self.world, "chat")
        def _chat(this, sender, message, *a):
            if not sender or sender == self.username:
                return
            self._push(self._relay(f"💬 **{sender}**: {message}"))
            if self.groq and message.lower().startswith("miku"):
                req = message[4:].strip(" ,:!")
                if req:
                    self._push(self._think(req, sender))

        @On(self.world, "death")
        def _death(this):
            self._push(self._relay(f"💀 **{self.username}** è morta"))

        @On(self.world, "kicked")
        def _kicked(this, reason, *a):
            self._push(self._relay(f"🚫 Kickata: {reason}"))

        @On(self.world, "end")
        def _end(this, *a):
            self.world = None
            self._push(self._relay("🔴 Disconnessa da Minecraft"))

    def _goto(self, x, y, z):
        self.world.pathfinder.setMovements(self.movements)
        self.world.pathfinder.setGoal(self.pf.goals.GoalNear(x, y, z, 1))

    def _come(self, player):
        p = self.world.players[player]
        if not p or not p.entity:
            return False
        pos = p.entity.position
        self._goto(pos.x, pos.y, pos.z)
        return True

    def _follow(self, player):
        p = self.world.players[player]
        if not p or not p.entity:
            return False
        self.world.pathfinder.setMovements(self.movements)
        self.world.pathfinder.setGoal(self.pf.goals.GoalFollow(p.entity, 2), True)
        return True

    def _stop(self):
        self.world.pathfinder.setGoal(None)

    @mc.command(description="Connetti il bot al server Minecraft")
    async def connect(self, interaction: discord.Interaction):
        if self.world:
            await interaction.response.send_message("Sono già dentro.", ephemeral=True)
            return
        await interaction.response.defer()
        await asyncio.to_thread(self._connect)
        await interaction.followup.send(f"Mi connetto a `{self.host}:{self.port}` come **{self.username}**...")

    @mc.command(description="Disconnetti il bot dal server")
    async def disconnect(self, interaction: discord.Interaction):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        self.world.quit()
        self.world = None
        await interaction.response.send_message("Esco da Minecraft. 👋")

    @mc.command(description="Stato della connessione Minecraft")
    async def status(self, interaction: discord.Interaction):
        if not self.world:
            await interaction.response.send_message("🔴 Non connessa.", ephemeral=True)
            return
        players = ", ".join(str(p) for p in self.world.players) or "nessuno"
        await interaction.response.send_message(f"🟢 Connessa come **{self.username}**.\nGiocatori online: {players}")

    @mc.command(description="Fai scrivere un messaggio in chat Minecraft")
    async def say(self, interaction: discord.Interaction, testo: str):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        self.world.chat(testo)
        await interaction.response.send_message(f"📣 `{testo}`")

    @mc.command(description="Vai a delle coordinate")
    async def goto(self, interaction: discord.Interaction, x: float, y: float, z: float):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        self._goto(x, y, z)
        await interaction.response.send_message(f"🚶 Vado a `{x} {y} {z}`")

    @mc.command(description="Raggiungi un giocatore")
    async def come(self, interaction: discord.Interaction, giocatore: str):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        if not self._come(giocatore):
            await interaction.response.send_message(f"Non vedo **{giocatore}**.", ephemeral=True)
            return
        await interaction.response.send_message(f"🚶 Arrivo da **{giocatore}**")

    @mc.command(description="Segui un giocatore")
    async def follow(self, interaction: discord.Interaction, giocatore: str):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        if not self._follow(giocatore):
            await interaction.response.send_message(f"Non vedo **{giocatore}**.", ephemeral=True)
            return
        await interaction.response.send_message(f"🐾 Seguo **{giocatore}**")

    @mc.command(description="Fermati")
    async def stop(self, interaction: discord.Interaction):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        self._stop()
        await interaction.response.send_message("✋ Fermo qui.")

    @mc.command(description="Chiedi a Miku in linguaggio naturale")
    async def ask(self, interaction: discord.Interaction, richiesta: str):
        if not self.groq:
            await interaction.response.send_message("LLM non configurato (manca GROQ_API_KEY).", ephemeral=True)
            return
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        await interaction.response.defer()
        out = await self._think(richiesta)
        await interaction.followup.send(out)

    async def _think(self, prompt, who=None):
        ctx = prompt if not who else f"[{who} dice] {prompt}"
        try:
            resp = await self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": ctx}],
                tools=TOOLS, tool_choice="auto", temperature=0,
            )
        except Exception as e:
            self.world.chat("mi sa che groq è morto")
            return f"Errore LLM: {e}"
        msg = resp.choices[0].message
        done = []
        for tc in msg.tool_calls or []:
            args = json.loads(tc.function.arguments or "{}")
            if who and tc.function.name in ("come", "follow") and not args.get("player"):
                args["player"] = who
            done.append(self._dispatch(tc.function.name, args))
        if msg.content:
            done.append(msg.content)
        reply = " ".join(p for p in done if p) or "boh non ho capito"
        self.world.chat(reply[:240])
        return reply

    def _dispatch(self, name, args):
        if name == "say":
            return args["text"]
        if name == "goto":
            self._goto(args["x"], args["y"], args["z"])
            return f"🚶 Vado a `{args['x']} {args['y']} {args['z']}`"
        if name == "come":
            ok = self._come(args["player"])
            return f"🚶 Arrivo da **{args['player']}**" if ok else f"Non vedo **{args['player']}**"
        if name == "follow":
            ok = self._follow(args["player"])
            return f"🐾 Seguo **{args['player']}**" if ok else f"Non vedo **{args['player']}**"
        if name == "stop":
            self._stop()
            return "✋ Fermo."
        return f"Tool sconosciuto: {name}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.world:
            return
        if self.relay_id and message.channel.id == self.relay_id and not message.content.startswith("/"):
            self.world.chat(f"<{message.author.display_name}> {message.content}")


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
