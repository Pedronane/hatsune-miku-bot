# Discord Server Bot

Bot Discord per un server privato di **10 amici IRL** (soli uomini, nessun tema "inclusività/pronomi"). Tono dei messaggi verso gli utenti: **italiano slang/ironico tra amici**.

## Stack

- **discord.py** 2.x (Python 3.14), slash commands (`app_commands`)
- **SQLite** per persistenza (XP, config, moderazione) — file locale, no server DB
- **yt-dlp + ffmpeg** per musica da YouTube
- **mineflayer** (via pacchetto Python `javascript`/JSPyBridge → Node) per il bot Minecraft
- **Groq** (`AsyncGroq`, free-tier) per `/mc ask` linguaggio naturale → tool calling
- Hosting target: **Raspberry/hardware dedicato sempre acceso** (systemd service)
- Segreti in `.env` (`DISCORD_TOKEN`, `MC_*`, `GROQ_API_KEY`), caricati con python-dotenv

## Architettura

Cogs separati, un file per modulo in `cogs/`:

| Cog | Contenuto |
|-----|-----------|
| `music.py` | Play/queue/skip da YouTube (yt-dlp + ffmpeg) |
| `xp.py` | XP per messaggi, comando `/top` (classifica). **Nessun ruolo automatico** |
| `mod.py` | Moderazione **completa**: kick/ban/mute, automod (spam/link/parolacce), warn system, mute temporanei, anti-raid, log azioni |
| `fun.py` | `/poll`, `/roll`, `/scegli`, `8ball`, meme/gif, mini-giochi (trivia, impiccato, tris) |
| `minecraft.py` | bot Minecraft quasi-autonomo. `/mc` (connect/say/goto/come/follow/stop/collect/craft/ask) + chat in-game "miku ...". mineflayer+plugin dentro Python (JSPyBridge). Skill deterministiche (collect legna, craft da zero→piccone) + LLM router Groq. **Vedi `docs/BOT_MINECRAFT.md` per architettura, stato step-by-step e gotcha (versione≤1.21.8, timeout JSPyBridge, deploy package.json).** |

`bot.py` = entrypoint: carica i cog, gestisce intents e sync degli slash command.

## Comandi

- **Solo slash command** (`/`). Niente prefisso `!`.
- I vecchi comandi a prefisso (`!setup`, `!nuke`, `!makeroles`, `!say`, `!embed`, `!backup`) vanno **rimossi** — il server è già configurato.

## Convenzioni codice

- No commenti, no docstring, no error handling per casi impossibili
- Edit > nuovi file; niente feature extra non richieste
- Verifica reale (avvio bot + test) prima di dire "fatto"
- Libreria/framework → consulta docs aggiornate (context7/find-docs) prima di scrivere

## Repo

Pubblica: https://github.com/Pedronane/discord-server-bot
`.env`, `config.json`, `venv/`, `backup_*.json` esclusi da git. **Mai committare il token.**
