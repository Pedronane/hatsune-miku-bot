import json
import os
import random
import re

import aiohttp
import discord
from discord.ext import commands

import db

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
TRIGGER = re.compile(r"\bmiku\b", re.IGNORECASE)
TEXT_CALL = re.compile(r"<function=(\w+)\s*>?\s*(\{.*?\})?", re.DOTALL)
CLEAN_FULL = re.compile(r"<function=\w+[\s>]*\{.*?\}[\s>]*(?:</function>)?", re.DOTALL)
CLEAN_BARE = re.compile(r"<function=\w+[\s>]*(?:</function>)?", re.DOTALL)
SYSTEM = (
    "Sei Hatsune Miku, la vocaloid idol con i twin-tail turchesi, su un server Discord "
    "privato di soli ragazzi amici. Parli SEMPRE in italiano, tono slang ironico, allegra e "
    "un po' cringe-kawaii, ogni tanto emoji 🎵💙 o un 'nya'/'~'. Risposte CORTE (max 2-3 frasi). "
    "Niente disclaimer, niente 'come AI/assistente'. "
    "Sei anche il DJ del server: se ti chiedono di mettere/saltare/fermare/mettere in pausa musica, "
    "alzare o abbassare il volume, vedere la coda, attivare loop o shuffle, USA gli strumenti a disposizione. "
    "Dopo aver eseguito un'azione, commentala in UNA frase restando nel personaggio."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "play", "description": "Mette in riproduzione o accoda una canzone da YouTube (nome o link).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Titolo, artista o link YouTube della canzone"}},
            "required": ["query"]}}},
    {"type": "function", "function": {"name": "skip", "description": "Salta il brano corrente.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "pause", "description": "Mette in pausa la musica.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "resume", "description": "Riprende la musica in pausa.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "stop", "description": "Ferma la musica e svuota la coda.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "shuffle", "description": "Mescola la coda.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "set_loop", "description": "Imposta la ripetizione.",
        "parameters": {"type": "object", "properties": {
            "mode": {"type": "string", "enum": ["off", "brano", "coda"]}}, "required": ["mode"]}}},
    {"type": "function", "function": {
        "name": "set_volume", "description": "Imposta il volume in percentuale (0-200).",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "description": "Volume 0-200"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "show_queue", "description": "Mostra la coda attuale.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "leave", "description": "Esce dal canale vocale.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "ricorda",
        "description": "Salva in memoria permanente un fatto importante su un utente o sul server (preferenze, soprannomi, eventi). Usalo quando impari qualcosa che vale la pena ricordare nel tempo.",
        "parameters": {"type": "object", "properties": {
            "fatto": {"type": "string", "description": "Il fatto da ricordare, frase breve e chiara con il nome di chi riguarda"}},
            "required": ["fatto"]}}},
]


class Miku(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = os.environ.get("GROQ_API_KEY")

    async def groq(self, messages, tools=None):
        payload = {"model": MODEL, "messages": messages, "temperature": 0.8, "max_tokens": 400}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as s:
            async with s.post(GROQ_URL, headers=headers, json=payload) as r:
                data = await r.json()
        return data["choices"][0]["message"]

    def text_calls(self, content):
        out = []
        for name, js in TEXT_CALL.findall(content or ""):
            try:
                args = json.loads(js) if js else {}
            except Exception:
                args = {}
            out.append((name, args))
        return out

    def clean(self, content):
        if not content:
            return ""
        content = CLEAN_FULL.sub("", content)
        content = CLEAN_BARE.sub("", content)
        return content.replace("</function>", "").strip()

    async def run_tool(self, message, name, args):
        music = self.bot.get_cog("Music")
        guild = message.guild
        gid = guild.id
        vc = guild.voice_client
        if name == "play":
            if await music.connect_member(message.author) is None:
                return "Errore: chi ha chiesto la canzone non è in un canale vocale."
            track, started = await music.enqueue(message.author, args["query"])
            return f"{'Ora suona' if started else 'Aggiunto in coda'}: {track.title}"
        if name == "skip":
            if vc and vc.is_playing():
                vc.stop()
                return "Brano skippato."
            return "Non sta suonando niente."
        if name == "pause":
            if vc and vc.is_playing():
                vc.pause()
                return "Musica in pausa."
            return "Non sta suonando niente."
        if name == "resume":
            if vc and vc.is_paused():
                vc.resume()
                return "Musica ripresa."
            return "Niente in pausa."
        if name == "stop":
            music.queues[gid].clear()
            music.loop_modes[gid] = "off"
            music.current[gid] = None
            if vc:
                vc.stop()
            return "Fermato tutto, coda svuotata."
        if name == "shuffle":
            q = music.queues[gid]
            if len(q) < 2:
                return "Coda troppo corta per mescolare."
            random.shuffle(q)
            return f"Coda mescolata ({len(q)} brani)."
        if name == "set_loop":
            mode = {"off": "off", "brano": "one", "coda": "all"}.get(args.get("mode"), "off")
            music.loop_modes[gid] = mode
            return f"Loop impostato su {args.get('mode')}."
        if name == "set_volume":
            lvl = max(0, min(200, int(args.get("level", 100))))
            music.volumes[gid] = lvl / 100
            if vc and vc.source:
                vc.source.volume = lvl / 100
            return f"Volume a {lvl}%."
        if name == "show_queue":
            cur = music.current.get(gid)
            q = music.queues[gid]
            if not cur and not q:
                return "Coda vuota."
            parts = []
            if cur:
                parts.append(f"Ora suona: {cur.title}")
            parts += [f"{i + 1}. {t.title}" for i, t in enumerate(q[:10])]
            return " | ".join(parts)
        if name == "leave":
            if vc:
                music.queues[gid].clear()
                music.loop_modes[gid] = "off"
                music.current[gid] = None
                await vc.disconnect()
                return "Uscita dal vocale."
            return "Non sono in nessun vocale."
        if name == "ricorda":
            db.add_fact(gid, args["fatto"])
            return f"Memorizzato: {args['fatto']}"
        return "Azione sconosciuta."

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if not TRIGGER.search(message.content):
            return
        if not self.key:
            return
        gid = message.guild.id
        cid = message.channel.id
        sys = SYSTEM
        facts = db.get_facts(gid)
        if facts:
            sys += "\n\nCose che ricordi (memoria permanente):\n" + "\n".join(f"- {f['fact']}" for f in facts)
        user_msg = f"{message.author.display_name}: {message.content}"
        msgs = [{"role": "system", "content": sys}]
        for h in db.get_history(cid):
            msgs.append({"role": h["role"], "content": h["content"]})
        msgs.append({"role": "user", "content": user_msg})
        async with message.channel.typing():
            try:
                m = await self.groq(msgs, TOOLS)
                if m.get("tool_calls"):
                    msgs.append(m)
                    for tc in m["tool_calls"]:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                        result = await self.run_tool(message, tc["function"]["name"], args)
                        msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                    m = await self.groq(msgs)
                elif self.text_calls(m.get("content")):
                    results = [await self.run_tool(message, n, a) for n, a in self.text_calls(m.get("content"))]
                    msgs.append({"role": "user", "content": "Risultato comandi: " + " | ".join(results) + ". Rispondi in personaggio in 1 frase."})
                    m = await self.groq(msgs)
                reply = self.clean(m.get("content")) or "🎵"
            except Exception:
                reply = "Ehm, mi si è inceppata la voce 🎵 riprova tra un po'~"
        db.add_history(cid, "user", user_msg)
        db.add_history(cid, "assistant", reply)
        await message.reply(reply[:2000], mention_author=False)


async def setup(bot):
    await bot.add_cog(Miku(bot))
