import asyncio
import json
import os
import re

import discord
from discord import app_commands
from discord.ext import commands

PERSONA = (
    "Sei Hatsune Miku, controlli un bot dentro Minecraft per un gruppo di amici. "
    "Strumenti: goto (vai a coordinate x y z), come (raggiungi un giocatore), "
    "follow (segui un giocatore), stop (fermati), say (parla in chat). "
    "Se ti chiedono un'azione nel gioco usa SEMPRE lo strumento giusto. "
    "I nomi dei giocatori sono username esatti. Se dicono 'vieni da me' o "
    "'raggiungimi' senza un nome usa come; se dicono 'seguimi' usa follow; col tuo giocatore. "
    "Quando rispondi a parole scrivi solo testo semplice, niente tag, virgolette o parentesi. "
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
        "name": "come", "description": "Raggiungi un giocatore una volta sola (vieni qui, raggiungimi)",
        "parameters": {"type": "object", "properties": {"player": {"type": "string"}}, "required": ["player"]}}},
    {"type": "function", "function": {
        "name": "follow", "description": "Segui di continuo un giocatore che si muove (seguimi, stammi dietro)",
        "parameters": {"type": "object", "properties": {"player": {"type": "string"}}, "required": ["player"]}}},
    {"type": "function", "function": {
        "name": "stop", "description": "Fermati, smetti di muoverti",
        "parameters": {"type": "object", "properties": {}}}},
]

# Step 4 — mining. Tier dei picconi (per harvestare serve un piccone >= tier del blocco).
PICK_TIER = {"wooden": 1, "golden": 1, "stone": 2, "iron": 3, "diamond": 4, "netherite": 5}
# Alias italiano/inglese -> nomi blocco Minecraft (varianti normale + deepslate).
MINE_ALIASES = {
    "pietra": ["stone"], "sasso": ["stone"], "stone": ["stone"], "cobblestone": ["stone"],
    "ferro": ["iron_ore", "deepslate_iron_ore"], "iron": ["iron_ore", "deepslate_iron_ore"],
    "carbone": ["coal_ore", "deepslate_coal_ore"], "coal": ["coal_ore", "deepslate_coal_ore"],
    "rame": ["copper_ore", "deepslate_copper_ore"], "copper": ["copper_ore", "deepslate_copper_ore"],
    "lapis": ["lapis_ore", "deepslate_lapis_ore"],
    "oro": ["gold_ore", "deepslate_gold_ore"], "gold": ["gold_ore", "deepslate_gold_ore"],
    "redstone": ["redstone_ore", "deepslate_redstone_ore"],
    "diamante": ["diamond_ore", "deepslate_diamond_ore"], "diamond": ["diamond_ore", "deepslate_diamond_ore"],
    "smeraldo": ["emerald_ore", "deepslate_emerald_ore"],
}
# Tier minimo di piccone per far droppare il blocco (mani nude / legno non bastano sui minerali).
ORE_TIER = {
    "stone": 1, "coal_ore": 1, "deepslate_coal_ore": 1,
    "iron_ore": 2, "deepslate_iron_ore": 2, "copper_ore": 2, "deepslate_copper_ore": 2,
    "lapis_ore": 2, "deepslate_lapis_ore": 2,
    "gold_ore": 3, "deepslate_gold_ore": 3, "redstone_ore": 3, "deepslate_redstone_ore": 3,
    "diamond_ore": 3, "deepslate_diamond_ore": 3, "emerald_ore": 3, "deepslate_emerald_ore": 3,
}


class Minecraft(commands.Cog):
    mc = app_commands.Group(name="mc", description="Controlla il bot dentro Minecraft")

    def __init__(self, bot):
        self.bot = bot
        self.host = os.environ.get("MC_HOST", "localhost")
        self.port = int(os.environ.get("MC_PORT", "25565"))
        self.username = os.environ.get("MC_USERNAME", "Miku")
        self.version = os.environ.get("MC_VERSION") or False
        self.relay_id = int(os.environ.get("MC_RELAY_CHANNEL_ID", "0"))
        # Trigger LLM da chat IN-GAME: OFF di default. Il server è offline-mode,
        # chiunque può entrare con qualsiasi nome e pilotare il bot → tienilo spento.
        # /mc ask da Discord resta sempre attivo (lì gli utenti sono autenticati).
        self.ingame_llm = os.environ.get("MC_INGAME_LLM", "").lower() in ("1", "true", "yes", "on")
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
                await ch.send(text[:2000], allowed_mentions=discord.AllowedMentions.none())

    def _safe_chat(self, text):
        # Mai mandare comandi di gioco: una stringa che inizia con "/" verrebbe
        # eseguita come comando Minecraft (es. /op, /kill). I newline NON vanno
        # lasciati passare: bot.chat() spezza sui "\n" e invia ogni riga separata,
        # così una seconda riga "/op tizio" verrebbe eseguita aggirando il check.
        text = re.sub(r"\s+", " ", str(text)).strip()
        if text.startswith("/"):
            text = "​" + text
        if self.world:
            self.world.chat(text[:240])

    def _require(self):
        if self.lib is None:
            from javascript import require
            self.lib = require("mineflayer")
            self.pf = require("mineflayer-pathfinder")
            self.collectblock = require("mineflayer-collectblock")
            self.tool = require("mineflayer-tool")
            self.pvp = require("mineflayer-pvp")
            self.armor = require("mineflayer-armor-manager")
            self.autoeat = require("mineflayer-auto-eat")
            self.vec3 = require("vec3")

    def _connect(self):
        from javascript import On
        self._require()
        self.world = self.lib.createBot({
            "host": self.host, "port": self.port,
            "username": self.username, "auth": "offline", "version": self.version,
        })
        self.world.loadPlugin(self.pf.pathfinder)
        self.world.loadPlugin(self.collectblock.plugin)
        self.world.loadPlugin(self.tool.plugin)
        self.world.loadPlugin(self.pvp.plugin)
        self.world.loadPlugin(self.armor)
        self.world.loadPlugin(self.autoeat.loader)

        @On(self.world, "spawn")
        def _spawn(this):
            self.movements = self.pf.Movements(self.world)
            self._push(self._relay(f"🟢 **{self.username}** spawnato in Minecraft"))

        @On(self.world, "chat")
        def _chat(this, sender, message, *a):
            if not sender or sender == self.username:
                return
            self._push(self._relay(f"💬 **{sender}**: {message}"))
            if self.ingame_llm and self.groq and message.lower().startswith("miku"):
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

    def _block_ids(self, what):
        w = what.lower().strip()
        logs = {"legna", "legno", "wood", "tronco", "tronchi", "log", "logs"}
        ids = []
        for b in self.world.registry.blocksArray:
            n = str(b.name)
            if w in logs:
                if n.endswith("_log"):
                    ids.append(b.id)
            elif w in n:
                ids.append(b.id)
        return ids

    def _collect_one(self, block):
        self.world.pathfinder.setMovements(self.movements)
        try:
            self.world.collectBlock.collect(block, {"ignoreNoPath": True}, timeout=300)
        except Exception as e:
            return str(e)
        return None

    def _collect(self, what="legna", count=1):
        ids = self._block_ids(what)
        if not ids:
            return f"non so cosa sia '{what}'"
        got = 0
        for dist in (48, 96, 160):
            found = self.world.findBlocks({"matching": ids, "maxDistance": dist, "count": count})
            n = int(found.length)
            for i in range(n):
                blk = self.world.blockAt(found[i])
                if blk is None:
                    continue
                err = self._collect_one(blk)
                if err:
                    return f"problema con {what}: {err[:80]}"
                got += 1
                if got >= count:
                    return f"raccolti {got} {what}"
            if got:
                return f"raccolti {got} {what}"
        return f"non trovo {what} qui intorno"

    def _inv(self):
        return self.world.inventory.items()

    def _count_suffix(self, suffix, exact=False):
        tot = 0
        for it in self._inv():
            n = str(it.name)
            if (n == suffix) if exact else n.endswith(suffix):
                tot += it.count
        return tot

    def _find_inv_item(self, suffix, exact=False):
        for it in self._inv():
            n = str(it.name)
            if (n == suffix) if exact else n.endswith(suffix):
                return it
        return None

    def _names_with(self, suffix):
        return [str(it.name) for it in self.world.registry.itemsArray if str(it.name).endswith(suffix)]

    def _item_id(self, name):
        o = self.world.registry.itemsByName[name]
        return o.id if o else None

    def _craft_one(self, item_name, table=None):
        iid = self._item_id(item_name)
        if iid is None:
            return False
        recs = self.world.recipesFor(iid, None, 1, table)
        if int(recs.length) == 0:
            return False
        self.world.craft(recs[0], 1, table, timeout=60)
        return True

    def _craft_any(self, suffix):
        for name in self._names_with(suffix):
            if self._craft_one(name):
                return True
        return False

    def _ensure_planks(self, n):
        for _ in range(30):
            if self._count_suffix("_planks") >= n:
                return True
            if self._count_suffix("_log") < 1:
                self._collect("legna", 1)
                if self._count_suffix("_log") < 1:
                    return False
            if not self._craft_any("_planks"):
                return False
        return self._count_suffix("_planks") >= n

    def _ensure_sticks(self, n):
        for _ in range(30):
            if self._count_suffix("stick", exact=True) >= n:
                return True
            if self._count_suffix("_planks") < 2 and not self._ensure_planks(2):
                return False
            if not self._craft_one("stick"):
                return False
        return self._count_suffix("stick", exact=True) >= n

    def _table_block(self):
        bid = self.world.registry.blocksByName["crafting_table"].id
        return self.world.findBlock({"matching": bid, "maxDistance": 4})

    def _relocate_open(self):
        pos = self.world.entity.position
        for dx, dz in ((3, 0), (0, 3), (-3, 0), (0, -3), (3, 3), (-3, -3)):
            t = pos.offset(dx, 0, dz)
            foot = self.world.blockAt(t)
            below = self.world.blockAt(t.offset(0, -1, 0))
            if foot and str(foot.name) == "air" and below and str(below.name) != "air":
                self.world.pathfinder.setMovements(self.movements)
                try:
                    self.world.pathfinder.goto(self.pf.goals.GoalBlock(t.x, t.y, t.z), timeout=40)
                except Exception:
                    pass
                return True
        return False

    def _place_table(self):
        item = self._find_inv_item("crafting_table", exact=True)
        if item is None:
            return False
        self.world.equip(item, "hand", timeout=20)
        for attempt in range(4):
            pos = self.world.entity.position
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                base = self.world.blockAt(pos.offset(dx, -1, dz))
                space = self.world.blockAt(pos.offset(dx, 0, dz))
                if base and str(base.name) != "air" and space and str(space.name) == "air":
                    try:
                        self.world.placeBlock(base, self.vec3(0, 1, 0), timeout=30)
                        return True
                    except Exception:
                        continue
            if not self._relocate_open():
                break
        return False

    def _ensure_table(self):
        b = self._table_block()
        if b:
            return b
        if self._find_inv_item("crafting_table", exact=True) is None:
            if not self._ensure_planks(4) or not self._craft_one("crafting_table"):
                return None
        if not self._place_table():
            return None
        return self._table_block()

    def _have_pickaxe_tier(self):
        best = 0
        for it in self._inv():
            n = str(it.name)
            if n.endswith("_pickaxe"):
                best = max(best, PICK_TIER.get(n[:-8], 0))
        return best

    def _ensure_wooden_pickaxe(self):
        if self._have_pickaxe_tier() >= 1:
            return True
        table = self._ensure_table()
        if table is None:
            return False
        if not self._ensure_sticks(2) or not self._ensure_planks(3):
            return False
        return self._craft_one("wooden_pickaxe", table)

    def _ensure_stone_pickaxe(self):
        if self._have_pickaxe_tier() >= 2:
            return True
        if not self._ensure_wooden_pickaxe():
            return False
        if self._count_suffix("cobblestone", exact=True) < 3:
            self._mine_raw(["stone"], 3)
        if self._count_suffix("cobblestone", exact=True) < 3 or not self._ensure_sticks(2):
            return False
        table = self._ensure_table()
        return bool(table) and self._craft_one("stone_pickaxe", table)

    def _ensure_pickaxe_tier(self, req):
        if self._have_pickaxe_tier() >= req:
            return True
        if req <= 1:
            return self._ensure_wooden_pickaxe()
        if req == 2:
            return self._ensure_stone_pickaxe()
        return False  # iron+ richiede fusione: non ancora implementata

    def _make_pickaxe(self):
        return "piccone di legno pronto!" if self._ensure_wooden_pickaxe() else "non riesco a fare il piccone"

    def _mine_raw(self, names, count):
        ids = []
        for nm in names:
            b = self.world.registry.blocksByName[nm]
            if b:
                ids.append(b.id)
        if not ids:
            return 0
        got = 0
        for dist in (32, 64, 128):
            found = self.world.findBlocks({"matching": ids, "maxDistance": dist, "count": max(count * 3, 10)})
            for i in range(int(found.length)):
                blk = self.world.blockAt(found[i])
                if blk is None:
                    continue
                # collectBlock equipaggia da sé il tool migliore (integra mineflayer-tool);
                # il tier del piccone è già garantito da _ensure_pickaxe_tier.
                if self._collect_one(blk) is None:
                    got += 1
                    if got >= count:
                        return got
            if got:
                return got
        return got

    def _mine(self, what="pietra", count=1):
        names = MINE_ALIASES.get(what.lower().strip())
        if not names:
            return f"non so minare '{what}'"
        req = max((ORE_TIER.get(n, 1) for n in names), default=1)
        if not self._ensure_pickaxe_tier(req):
            if req >= 3:
                return f"per {what} serve un piccone di ferro e non so ancora fonderlo"
            return f"non riesco a procurarmi il piccone adatto per {what}"
        got = self._mine_raw(names, count)
        if got >= count:
            return f"minati {got} {what}"
        if got:
            return f"minati solo {got}/{count} {what} qui intorno"
        return f"non trovo {what} qui intorno"

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
        self._safe_chat(testo)
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

    @mc.command(description="Raccogli blocchi (es. legna)")
    async def collect(self, interaction: discord.Interaction, cosa: str = "legna", quanti: int = 1):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        await interaction.response.defer()
        out = await asyncio.to_thread(self._collect, cosa, quanti)
        await interaction.followup.send(f"🪓 {out}")

    @mc.command(description="Fabbrica da zero (per ora: piccone di legno)")
    async def craft(self, interaction: discord.Interaction, oggetto: str = "piccone"):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        await interaction.response.defer()
        out = await asyncio.to_thread(self._make_pickaxe)
        await interaction.followup.send(f"🛠️ {out}")

    @mc.command(description="Scava pietra o minerali (si procura da sé il piccone giusto)")
    async def mine(self, interaction: discord.Interaction, cosa: str = "pietra", quanti: int = 1):
        if not self.world:
            await interaction.response.send_message("Non sono connessa.", ephemeral=True)
            return
        await interaction.response.defer()
        out = await asyncio.to_thread(self._mine, cosa, quanti)
        await interaction.followup.send(f"⛏️ {out}")

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
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if who and tc.function.name in ("come", "follow") and not args.get("player"):
                args["player"] = who
            done.append(self._dispatch(tc.function.name, args))
        if msg.content:
            done.append(self._clean(msg.content))
        reply = " ".join(p for p in done if p) or "boh non ho capito"
        self._safe_chat(reply)
        return reply

    def _clean(self, t):
        t = re.sub(r"</?[a-zA-Z]+>", "", t).strip()
        m = re.fullmatch(r'\{\s*"?(.*?)"?\s*\}', t, re.S)
        if m:
            t = m.group(1)
        t = re.sub(r'^\s*"?\w+"?\s*:\s*"?', "", t)
        return t.strip().strip('"')

    def _dispatch(self, name, args):
        if name == "say":
            return args.get("text", "")
        if name == "goto":
            try:
                x, y, z = float(args["x"]), float(args["y"]), float(args["z"])
            except (KeyError, TypeError, ValueError):
                return "coordinate non valide"
            self._goto(x, y, z)
            return f"🚶 Vado a `{x} {y} {z}`"
        if name in ("come", "follow"):
            player = args.get("player")
            if not player:
                return "quale giocatore?"
            ok = (self._come if name == "come" else self._follow)(player)
            verb = "Arrivo da" if name == "come" else "Seguo"
            return f"{'🚶' if name == 'come' else '🐾'} {verb} **{player}**" if ok else f"Non vedo **{player}**"
        if name == "stop":
            self._stop()
            return "✋ Fermo."
        return f"Tool sconosciuto: {name}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.world:
            return
        if self.relay_id and message.channel.id == self.relay_id and not message.content.startswith("/"):
            self._safe_chat(f"<{message.author.display_name}> {message.content}")


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
