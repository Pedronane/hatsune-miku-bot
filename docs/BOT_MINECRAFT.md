# Bot Minecraft "Hatsune Miku" — guida sviluppo

Cog `cogs/minecraft.py`: la bot Discord pilota un personaggio Minecraft via **mineflayer**, usato da
Python tramite **JSPyBridge** (pacchetto pip `javascript`, che spawna Node). Obiettivo finale: bot
quasi-autonomo che "fa quasi tutto", **low-token** (Groq free tier, modello `llama-3.1-8b-instant`).

## Architettura (3 livelli) — vedi piano in ~/.claude/plans/

1. **Skill deterministiche (0 token)** — funzioni Python nel cog che pilotano mineflayer+plugin.
2. **Loop sopravvivenza (0 token)** — auto-eat, fuga/combatti mob, anti-incastro. *(da fare, step 5)*
3. **LLM router sottile** — `_think` (Groq 8b) traduce linguaggio naturale → 1+ tool call. ~1 chiamata/comando.

Riferimento progettuale: **mindcraft** (mindcraft-bots/mindcraft). NON fare stile **Voyager** (genera codice → costoso).

## Stato avanzamento (step-by-step)

- [x] **Step 1** — plugin caricati: collectblock, tool, pvp, armor-manager, auto-eat
- [x] **Step 2** — skill `collect` (legna) + `/mc collect <cosa> <quanti>`
- [x] **Step 3** — crafting da zero → `wooden_pickaxe` + `/mc craft`. Catena: collect log → assi → bastoni → tavolo (place) → piccone
- [ ] **Step 4** — skill `mine` (pietra/minerali) con auto-tool + craft strumenti migliori
- [ ] **Step 5** — loop sopravvivenza (auto-eat + pvp + anti-incastro)
- [ ] **Step 6** — integrazione LLM: estendere `TOOLS`/`_dispatch`, esecutore lista-ordinata per obiettivi composti
- [ ] **Step 7** — self-play `/mc auto on|off` (loop throttlato 1 call/N min, spento di default)
- [ ] **Step 8** — README/DEPLOY finali

## Metodi chiave in `cogs/minecraft.py`

- `_require()` — require di mineflayer + tutti i plugin + `vec3`. Lazy (prima connessione).
- `_connect()` — createBot (offline), `loadPlugin` di tutti, registra eventi (`spawn/chat/death/kicked/end`).
- `_push(coro)` — marshalla una coroutine sul loop discord (le callback mineflayer girano su thread bridge!).
- Movimento: `_goto`, `_come`, `_follow`, `_stop` (pathfinder).
- Raccolta: `_collect(what,count)` → `_collect_one(block)` (collectBlock).
- Crafting: `_ensure_planks/_ensure_sticks`, `_ensure_table` → `_place_table`/`_relocate_open`, `_make_pickaxe`, `_craft_one`/`_craft_any`.
- LLM: `_think(prompt,who)`, `_dispatch(name,args)`, `_clean(text)`, `TOOLS`, `PERSONA`.

## ⚠️ Gotcha imparati a caro prezzo (LEGGERE prima di toccare)

1. **Versione MC**: mineflayer arriva max a **1.21.8**. Il mondo di test deve essere ≤ 1.21.8 (26.x NON supportato). `MC_VERSION=1.21.8` nel `.env`.
2. **Porta LAN cambia ogni apertura** del mondo singleplayer. Trovala con `ss -tlnp | grep java`. Aggiorna `MC_PORT`.
3. **JSPyBridge timeout default 10s** su OGNI chiamata JS. Operazioni lunghe (collect, craft, goto, equip, placeBlock) → passare `timeout=<secondi>` come kwarg, es. `bot.collectBlock.collect(b, opts, timeout=300)`. Unità = **secondi**.
4. **collectBlock.collect è promise-only**: niente callback (resta appeso). JSPyBridge blocca-e-risolve la promise da solo. Raccogliere **un blocco alla volta** (una lista Python NON si marshalla in array JS).
5. **recipesFor è inventory-aware** (ritorna solo ciò che puoi craftare ORA). Per la *definizione* di una ricetta usa `recipesAll(id, null, table)`. Quantità: `recipe.result.count`, ingredienti in `recipe.delta` (count negativi = consumati).
6. **Deploy / git pull abortisce**: `npm install` sul Pi modifica `package.json`/`package-lock.json` → `git pull --ff-only` fallisce. Fix: `git checkout -- package.json package-lock.json` PRIMA del pull.
7. **Bot si incastra tra gli alberi** dopo la raccolta → celle adiacenti occupate → placeBlock fallisce. `_place_table` ora si rilocà su terreno aperto (`_relocate_open`) e riprova.
8. **Offline LAN mantiene l'inventario** per username tra le riconnessioni (lo username del bot è `Hatsune_Miku`).
9. **Skin custom impossibile** su LAN/offline: serve PaperMC offline + SkinsRestorer, oppure account premium.

## Infra / deploy

- Pi **`bambu`** (Tailscale `100.125.120.14`), repo in `~/hatsune-miku-bot`, service systemd `discordbot`, utente `pietro`. Password sudo nota a Pietro.
- Mondo LAN sul PC **`yuki`** (`100.120.206.66`) → `MC_HOST=100.120.206.66`.
- `.env` sul Pi: `DISCORD_TOKEN`, `GROQ_API_KEY`, `MC_HOST/PORT/USERNAME/VERSION`, `MC_RELAY_CHANNEL_ID`.
- Deploy: in locale `git push`; sul Pi `git checkout -- package.json package-lock.json && git pull --ff-only && sudo systemctl restart discordbot`.

## Procedura di test (quella che funziona)

I test live girano sul Pi contro il mondo LAN aperto. Pattern:
1. Scrivere uno script in `/tmp/xxx.py` sul Pi che costruisce la cog a mano (`Minecraft.__new__`, set `lib/pf/collectblock/tool/pvp/armor/autoeat/vec3/world/movements`) e chiama il metodo skill.
2. Eseguire: `ssh bambu "cd ~/hatsune-miku-bot && PYTHONPATH=. timeout 220 ./venv/bin/python -u /tmp/xxx.py 2>&1 | grep -aE '^RES'"` in **foreground** (lo ssh in background è risultato instabile → exit 255).
3. Stampare righe `RES ...` con flush=True; verificare inventario before/after.
Esempi storici: `/tmp/mtest.py` (catena piccone), `/tmp/ptest.py` (placeBlock), `/tmp/rprobe2.py` (recipe).
