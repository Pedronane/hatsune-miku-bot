# Deploy sul Raspberry

Guida per far girare il bot 24/7 sul Raspberry. Eseguire tutti i comandi via SSH sul Raspberry.

## 1. Dipendenze di sistema

```bash
sudo apt update && sudo apt install -y git python3-venv ffmpeg
```

## 2. Clona e installa

```bash
cd ~
git clone https://github.com/Pedronane/discord-server-bot.git
cd discord-server-bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

> Se PyNaCl prova a compilare e fallisce (ARM 32-bit):
> `sudo apt install -y python3-dev libffi-dev libsodium-dev build-essential`

## 3. Token

```bash
cp .env.example .env
nano .env          # incolla DISCORD_TOKEN, poi Ctrl+O Invio Ctrl+X
```

## 4. Test manuale

```bash
./venv/bin/python bot.py
```

Deve stampare `Online come ...`. `Ctrl+C` per fermare.

## 5. Servizio systemd (avvio automatico + riavvio su crash)

```bash
sudo nano /etc/systemd/system/discordbot.service
```

Incolla (cambia `pi` se l'utente del Raspberry è diverso):

```ini
[Unit]
Description=Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/discord-server-bot
ExecStart=/home/pi/discord-server-bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Attiva:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now discordbot
sudo systemctl status discordbot
```

## Gestione

```bash
# log dal vivo
journalctl -u discordbot -f

# riavvia
sudo systemctl restart discordbot

# aggiorna all'ultima versione del repo
cd ~/discord-server-bot && git pull && sudo systemctl restart discordbot
```

## Checklist prima dell'avvio

- [ ] `.env` contiene il token vero
- [ ] 3 Privileged Gateway Intents attivi nel dev portal
- [ ] Bot invitato con scope `bot` + `applications.commands`
- [ ] `ffmpeg` installato (`ffmpeg -version`)
- [ ] `BADWORDS` in `cogs/mod.py` compilato (opzionale)
