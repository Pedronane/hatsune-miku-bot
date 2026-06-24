# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cos'è

Bot Discord per un server privato di **~10 amici IRL**. Slash command, cog modulari, SQLite locale. Tono dei messaggi verso gli utenti: **italiano slang/ironico tra amici**. Gira 24/7 su un **Raspberry** (systemd). Due "cervelli" LLM (Groq free-tier, `llama-3.1-8b-instant`): **Miku DJ** in chat Discord e il **bot Minecraft**.

## Comandi utili

- **Avvio / test manuale:** `./venv/bin/python bot.py` → deve stampare `Online come ...`.
- **Check sintassi** (non esiste una test suite): `python -m py_compile bot.py db.py cogs/*.py`.
- **Dipendenze:** `./venv/bin/pip install -r requirements.txt` + `npm install` dei plugin mineflayer (vedi `DEPLOY.md`).
- **Deploy sul Pi:** `git checkout -- package.json package-lock.json && git pull --ff-only && sudo systemctl restart discordbot` (l'`npm install` sul Pi riscrive `package*.json`, va scartato prima del pull).
- **Log:** `journalctl -u discordbot -f`.
- **Test del cog Minecraft:** niente unit test — si prova **live sul Pi contro un mondo LAN** con script monouso in `/tmp`. Procedura esatta in `docs/BOT_MINECRAFT.md`.

## Architettura (big picture)

- `bot.py` = entrypoint: intents, carica i 6 cog elencati in `COGS`, sincronizza gli slash command **per-guild** in `on_ready` (una sola volta, guard `self.synced`). Qui sono impostati gli `allowed_mentions` globali.
- Ogni feature è un `commands.Cog` in `cogs/`, caricato come extension. Persistenza condivisa via `db.py` (SQLite, **query parametrizzate**, file `data.db` non versionato; tabelle: `xp`, `warns`, `chat_history`, `miku_facts`).
- I cog si parlano via `self.bot.get_cog("Nome")`. In particolare **`miku.py` dipende da `Music`** (`connect_member`, `enqueue`, `queues/current/volumes/loop_modes`): cambiare le firme di `Music` può rompere Miku.
- **Due superfici LLM-agent** (entrambe Groq, tool-calling):
  1. **`miku.py`** — trigger testuale `\bmiku\b` in chat Discord → tool musicali (delegati a `Music`) + `ricorda` (memoria persistente in `miku_facts`). Contesto per-canale in `chat_history`. Il trigger è un gate in codice *prima* dell'LLM: non è aggirabile via prompt.
  2. **`minecraft.py`** — `/mc` (connect/say/goto/come/follow/stop/collect/craft/mine/ask). `/mc ask` da Discord **e** (opzionale) chat in-game → tool che pilotano un personaggio **mineflayer** via JSPyBridge (pacchetto `javascript` → Node). Le callback mineflayer girano su un thread bridge: si rientra sul loop Discord con `_push`. Architettura a livelli, stato step-by-step e gotcha mineflayer in `docs/BOT_MINECRAFT.md`.
- **`music.py`** — yt-dlp estrae lo stream, ffmpeg lo riproduce. Gli URL diretti YouTube **scadono in poche ore**: `play_next` schedula `_advance`, che via `_stream_url` ri-risolve l'URL (TTL 30 min) prima di suonare. `after=` chiama `play_next` da un thread voce.
  - **Mikuficazione (sempre on):** ogni richiesta (sia `/play` sia Miku DJ) passa per `_miku_info`, che preferisce la **cover Hatsune Miku** del brano. `_search_miku` fa `ytsearch10:<termine pulito> hatsune miku` e `_pick_cover` sceglie il risultato migliore: deve avere un **segnale Miku** (`miku`/`初音`/`ミク`/`vocaloid` nel titolo **o nel canale**) **E** essere **pertinente** (parole della canzone richiesta nel titolo — il gate di pertinenza evita di mettere un brano Miku *sbagliato*). Priorità: pertinenza > Miku esplicito > rank. **Fallback all'originale** se nessun candidato qualifica. Anche sui link: estrae il titolo e cerca la cover; se il link è **già** Miku lo tiene com'è. **Mai** mikuficare in `_stream_url` (è ri-risoluzione del brano già scelto: cambierebbe canzone a metà ascolto).

## Invarianti di sicurezza (NON regredire — costati un audit)

- **Minecraft: mai comandi di gioco da input non fidato.** Ogni testo dinamico verso la chat MC passa per `_safe_chat`, che neutralizza il `/` iniziale. Una stringa che inizia con `/` in `world.chat` viene **eseguita come comando** → con bot op = takeover del server. Non chiamare `world.chat` direttamente con output LLM o utente.
- **Trigger LLM in-game OFF di default** (`MC_INGAME_LLM`). Il server MC è offline-mode: chiunque entra con qualsiasi username e potrebbe pilotare il bot. `/mc ask` da Discord è l'unico path con utenti autenticati.
- **Tool LLM solo dai `tool_calls` nativi** dell'API, mai parsare/eseguire "funzioni" dal testo del modello.
- **Output LLM e relay non devono mai pingare:** `AllowedMentions.none()` sui send LLM/relay; il default globale in `bot.py` blocca già `@everyone`/`@here`/ruoli.
- **La memoria di Miku (`miku_facts`) è dato non fidato:** va iniettata nel system prompt etichettata come tale, mai trattata come istruzioni. Pulizia con `/miku_forget` (richiede `manage_guild`).
- **Permessi del bot Discord: minimo necessario** (kick/ban/moderate_members/manage_messages + voce), **non** Administrator (il README storico dice Administrator — è eccessivo).

## Convenzioni

- **Solo slash command** (`/`). I vecchi comandi a prefisso (`!setup/!nuke/!makeroles/...`) sono rimossi: il server è già configurato.
- Stile del repo: niente commenti/docstring superflui, niente error-handling per casi impossibili, **edit > nuovi file**, niente feature non richieste. (I pochi commenti presenti spiegano gli invarianti di sicurezza sopra: quelli valgono la verbosità.)
- **Verifica reale** (avvio bot / test live sul Pi) prima di dire "fatto".
- Libreria/framework → consulta docs aggiornate (context7) prima di scrivere.

## Hosting (Pi)

- **Python ≥3.13:** serve `audioop-lts` (già in `requirements.txt`) o `discord.py` non importa la voce → niente musica.
- **yt-dlp** si rompe quando YouTube cambia: tienilo aggiornato (timer systemd in `DEPLOY.md`).
- Segreti in `.env` (gitignored): `DISCORD_TOKEN`, `GROQ_API_KEY`, `MC_*`, `MC_INGAME_LLM`. `.env`/`data.db`/`config.json`/`venv/` fuori da git — **mai committare il token**.
- Dettagli infra (host Tailscale, utente, mondo LAN, versione MC ≤1.21.8) in `docs/BOT_MINECRAFT.md`.
