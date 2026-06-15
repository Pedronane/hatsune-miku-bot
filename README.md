# Discord Server Bot

Bot per setup e gestione di un server Discord: crea struttura (categorie, canali con emoji, ruoli), reaction roles, messaggio di benvenuto e comandi utility.

## Comandi

| Comando | Cosa fa |
|---------|---------|
| `!setup` | Crea categorie, canali (con emoji), ruoli base, reaction roles e welcome |
| `!makeroles` | Crea un pack di ruoli colorati |
| `!say #canale testo` | Posta un messaggio come il bot |
| `!embed #canale "titolo" testo` | Posta un embed |
| `!backup` | Salva la struttura del server in JSON |
| `!nuke confirm` | ⚠️ Cancella tutti i canali e ruoli (irreversibile) |

Tutti i comandi richiedono permessi da amministratore.

## Setup

1. Crea l'app e il bot su https://discord.com/developers/applications
2. Attiva i 3 **Privileged Gateway Intents** (Presence, Server Members, Message Content)
3. Invita il bot con scope `bot` e permesso Administrator
4. Configura il token:

```bash
cp .env.example .env
# incolla il token in .env
```

5. Installa e avvia:

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python bot.py
```

## Note

`.env` (token) e `config.json` sono esclusi da git. Non committare mai il token.
