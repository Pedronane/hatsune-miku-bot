import html
import random
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

EIGHTBALL = [
    "Ovvio sì.", "Manco per il cazzo.", "Boh, chiedi a tua madre.", "Sì ma non dirlo a nessuno.",
    "Assolutamente no.", "Forse, dipende quanto paghi.", "Le stelle dicono sì.", "Nì.",
    "Col cazzo.", "Sicuro al 1000%.", "Ho i miei dubbi, fra.", "Non ci contare.",
]

NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class TrisButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="​", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.current:
            await interaction.response.send_message("Non è il tuo turno, calmo.", ephemeral=True)
            return
        mark = "❌" if view.current == view.p1 else "⭕"
        self.label = mark
        self.style = discord.ButtonStyle.danger if mark == "❌" else discord.ButtonStyle.success
        self.disabled = True
        view.board[self.y][self.x] = mark
        winner = view.check()
        if winner:
            for child in view.children:
                child.disabled = True
            view.stop()
            await interaction.response.edit_message(
                content=f"🎉 Ha vinto {view.current.mention}!", view=view
            )
            return
        if all(c.disabled for c in view.children):
            view.stop()
            await interaction.response.edit_message(content="Pareggio. Che noia.", view=view)
            return
        view.current = view.p2 if view.current == view.p1 else view.p1
        await interaction.response.edit_message(
            content=f"Tris — tocca a {view.current.mention} ({'❌' if view.current == view.p1 else '⭕'})",
            view=view,
        )


class TrisView(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.current = p1
        self.board = [["", "", ""] for _ in range(3)]
        for y in range(3):
            for x in range(3):
                self.add_item(TrisButton(x, y))

    def check(self):
        b = self.board
        lines = b + [list(col) for col in zip(*b)] + [[b[i][i] for i in range(3)], [b[i][2 - i] for i in range(3)]]
        for line in lines:
            if line[0] and line[0] == line[1] == line[2]:
                return True
        return False


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Lancia un sondaggio")
    @app_commands.describe(domanda="La domanda", opzioni="Opzioni separate da virgola (vuoto = sì/no)")
    async def poll(self, interaction: discord.Interaction, domanda: str, opzioni: str = ""):
        opts = [o.strip() for o in opzioni.split(",") if o.strip()]
        if len(opts) > 10:
            await interaction.response.send_message("Max 10 opzioni, fra.", ephemeral=True)
            return
        if opts:
            desc = "\n".join(f"{NUMBERS[i]} {o}" for i, o in enumerate(opts))
            emojis = NUMBERS[: len(opts)]
        else:
            desc = "👍 Sì\n👎 No"
            emojis = ["👍", "👎"]
        embed = discord.Embed(title=f"📊 {domanda}", description=desc, colour=discord.Colour.blurple())
        embed.set_footer(text=f"Sondaggio di {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for e in emojis:
            await msg.add_reaction(e)

    @app_commands.command(description="Tira i dadi, es: 2d6")
    async def roll(self, interaction: discord.Interaction, dadi: str = "1d6"):
        m = re.fullmatch(r"(\d*)d(\d+)", dadi.lower())
        if not m:
            await interaction.response.send_message("Formato: `NdM` tipo `2d20`.", ephemeral=True)
            return
        n = int(m.group(1) or 1)
        faces = int(m.group(2))
        if not (1 <= n <= 100 and 2 <= faces <= 1000):
            await interaction.response.send_message("Numeri sensati per favore.", ephemeral=True)
            return
        rolls = [random.randint(1, faces) for _ in range(n)]
        await interaction.response.send_message(
            f"🎲 {dadi} → {' + '.join(map(str, rolls))} = **{sum(rolls)}**"
        )

    @app_commands.command(description="Scelgo io per te, indeciso del cazzo")
    async def scegli(self, interaction: discord.Interaction, opzioni: str):
        opts = [o.strip() for o in re.split(r"[,]| o ", opzioni) if o.strip()]
        if len(opts) < 2:
            await interaction.response.send_message("Dammi almeno 2 opzioni separate da virgola.", ephemeral=True)
            return
        await interaction.response.send_message(f"🤔 Scelgo... **{random.choice(opts)}**")

    @app_commands.command(name="8ball", description="Chiedi alla palla magica")
    async def eightball(self, interaction: discord.Interaction, domanda: str):
        await interaction.response.send_message(f"🎱 *{domanda}*\n> {random.choice(EIGHTBALL)}")

    @app_commands.command(description="Un meme a caso")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://meme-api.com/gimme") as r:
                    data = await r.json()
            embed = discord.Embed(title=data["title"], colour=discord.Colour.random())
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"r/{data['subreddit']}")
        except Exception:
            await interaction.followup.send("❌ Niente meme, l'API fa i capricci. Riprova.")
            return
        await interaction.followup.send(embed=embed)

    @app_commands.command(description="Sfida qualcuno a tris")
    async def tris(self, interaction: discord.Interaction, avversario: discord.Member):
        if avversario.bot or avversario == interaction.user:
            await interaction.response.send_message("Scegli un avversario vero.", ephemeral=True)
            return
        view = TrisView(interaction.user, avversario)
        await interaction.response.send_message(
            f"Tris: {interaction.user.mention} (❌) vs {avversario.mention} (⭕)\n"
            f"Tocca a {interaction.user.mention}",
            view=view,
        )

    @app_commands.command(description="Quiz a risposta multipla")
    async def trivia(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://opentdb.com/api.php?amount=1&type=multiple") as r:
                    data = await r.json()
            q = data["results"][0]
            question = html.unescape(q["question"])
            correct = html.unescape(q["correct_answer"])
            answers = [html.unescape(a) for a in q["incorrect_answers"]] + [correct]
        except Exception:
            await interaction.followup.send("❌ Niente quiz, l'API è giù. Riprova.")
            return
        random.shuffle(answers)

        view = discord.ui.View(timeout=30)
        answered = {}

        def make_cb(ans):
            async def cb(inter):
                if ans == correct:
                    await inter.response.send_message(f"✅ {inter.user.mention} esatto: **{correct}**")
                else:
                    await inter.response.send_message(f"❌ {inter.user.mention} sbagliato.", ephemeral=True)
                answered[inter.user.id] = ans
            return cb

        for ans in answers:
            btn = discord.ui.Button(label=ans[:80], style=discord.ButtonStyle.primary)
            btn.callback = make_cb(ans)
            view.add_item(btn)
        await interaction.followup.send(f"🧠 **{question}**", view=view)


async def setup(bot):
    await bot.add_cog(Fun(bot))
