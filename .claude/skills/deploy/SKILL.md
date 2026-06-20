---
name: deploy
description: Deploya l'ultima versione del bot sul Raspberry Pi (git pull + restart systemd) via SSH. Usa quando hai pushato le modifiche e vuoi pubblicarle in produzione.
disable-model-invocation: true
---

# Deploy sul Pi

Pubblica la versione corrente (già **pushata** su GitHub) sul Raspberry e riavvia il servizio.

## Prerequisiti
- Le modifiche sono su GitHub (il Pi fa `git pull`, non riceve il working tree locale).
- Accesso SSH al Pi: host `bambu` (Tailscale), repo in `~/hatsune-miku-bot`, service `discordbot`, utente `pietro`.

## Procedura
L'`npm install` sul Pi sporca `package.json`/`package-lock.json` → vanno scartati prima del pull, altrimenti `git pull --ff-only` aborta.

```bash
ssh bambu "cd ~/hatsune-miku-bot \
  && git checkout -- package.json package-lock.json \
  && git pull --ff-only \
  && sudo systemctl restart discordbot \
  && sleep 3 && systemctl is-active discordbot"
```

Deve stampare `active`. Poi controlla i log:

```bash
ssh bambu "journalctl -u discordbot -n 30 --no-pager"
```

Cerca `Online come ...`. Se vedi un traceback, il bot è ripartito ma un cog ha fallito il load → leggi l'errore e fixa prima di chiudere.

## Se hai cambiato dipendenze
- Python: `ssh bambu "cd ~/hatsune-miku-bot && ./venv/bin/pip install -r requirements.txt"` prima del restart.
- Node (mineflayer): `ssh bambu "cd ~/hatsune-miku-bot && npm install"` (poi ricordati il `git checkout -- package*.json` al prossimo deploy).
