# Discord Server Bot

Bot Discord per un server privato tra amici. Slash command, cog modulari, SQLite. Tono italiano scherzoso.

## Comandi (slash `/`)

**🎵 Musica** (serve ffmpeg sull'host)
- `/play <brano>` — nome o link YouTube
- `/skip` `/stop` `/queue` `/leave`

**📊 XP**
- `/rank` — i tuoi punti
- `/top` — classifica

**🎲 Fun**
- `/poll <domanda> [opzioni]` `/roll <NdM>` `/scegli <opzioni>` `/8ball <domanda>`
- `/meme` `/trivia` `/tris <avversario>`

**🛡️ Moderazione** (richiede permessi adeguati)
- `/kick` `/ban` `/unban` `/mute <durata>` `/unmute`
- `/warn` `/warnings` `/purge <n>`
- Automod automatico: spam, invite link, parole vietate, anti-raid → log nel canale con "log" nel nome

**⛏️ Minecraft** (server in offline-mode + Node sull'host)
- `/mc connect` `/mc disconnect` `/mc status`
- `/mc say <testo>` — scrive in chat MC
- `/mc goto <x> <y> <z>` `/mc come <giocatore>` `/mc follow <giocatore>` `/mc stop`
- `/mc ask <frase>` — linguaggio naturale → azioni (persona "Miku", LLM Groq free-tier)
- Ponte chat: in-game ↔ canale Discord (`MC_RELAY_CHANNEL_ID`)

## Struttura

```
bot.py          entrypoint, carica i cog e sincronizza gli slash
db.py           SQLite (xp, warns)
cogs/
  music.py      yt-dlp + ffmpeg
  xp.py         XP per messaggi + classifica
  mod.py        moderazione completa + automod
  fun.py        giochi e utility
  minecraft.py  bot Minecraft (mineflayer via JSPyBridge) + ponte chat + LLM Groq
```

## Setup

1. App + bot su https://discord.com/developers/applications
2. Attiva i 3 **Privileged Gateway Intents**
3. Invita con scope `bot` + `applications.commands`, permesso Administrator
4. Configura ed esegui:

```bash
cp .env.example .env          # incolla il token
python -m venv venv
./venv/bin/pip install -r requirements.txt
sudo apt install ffmpeg nodejs npm   # ffmpeg=musica, node=cog Minecraft
npm install mineflayer mineflayer-pathfinder
./venv/bin/python bot.py
```

Per il cog Minecraft, in `.env`: `MC_HOST`, `MC_PORT`, `MC_USERNAME`, `MC_RELAY_CHANNEL_ID` e `GROQ_API_KEY` (gratis su console.groq.com). Server MC in **offline-mode**.

Gli slash command vengono sincronizzati al primo avvio su ogni server.

## Servizio systemd (host sempre acceso)

```ini
# /etc/systemd/system/discordbot.service
[Unit]
Description=Discord Bot
After=network.target

[Service]
WorkingDirectory=/home/pi/discord-bot
ExecStart=/home/pi/discord-bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now discordbot
```

## Note

- `BADWORDS` in `cogs/mod.py` è un placeholder: metti le parole che vuoi filtrare.
- `.env`, `data.db`, `config.json` esclusi da git. **Mai committare il token.**
