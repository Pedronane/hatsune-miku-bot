---
name: mc-test
description: Testa una skill del cog Minecraft live sul Pi contro il mondo LAN con uno script monouso. Usa quando modifichi cogs/minecraft.py e devi verificare collect/craft/movimento/pathfinding.
disable-model-invocation: true
---

# Test live del cog Minecraft

Non ci sono unit test: le skill mineflayer si provano sul Pi contro un **mondo LAN aperto**. Marshalling e timing JSPyBridge si rompono solo dal vivo.

## Setup
- Mondo LAN aperto sul PC `yuki` (Tailscale), versione **≤ 1.21.8**.
- La porta LAN **cambia a ogni apertura** del mondo → trovala e aggiorna `MC_PORT` nel `.env` del Pi:
  ```bash
  ssh yuki "ss -tlnp | grep java"
  ```

## Pattern (script monouso)
Costruisci la cog **senza** Discord, settando a mano i riferimenti mineflayer, e chiama il metodo skill:

```python
# /tmp/test.py sul Pi
from cogs.minecraft import Minecraft
m = Minecraft.__new__(Minecraft)
# ... set manuale: m.lib, m.pf, m.collectblock, m.tool, m.pvp, m.armor,
#     m.autoeat, m.vec3, m.world, m.movements (vedi _require/_connect)
print("RES", m._collect("legna", 1), flush=True)   # esempio
```

Stampa righe `RES ...` con `flush=True` e controlla l'inventario before/after.

## Esecuzione (foreground!)
L'ssh in background è instabile (exit 255) → sempre in foreground:

```bash
ssh bambu "cd ~/hatsune-miku-bot && PYTHONPATH=. timeout 220 ./venv/bin/python -u /tmp/test.py 2>&1 | grep -aE '^RES'"
```

## Promemoria gotcha (dettagli in docs/BOT_MINECRAFT.md)
- Operazioni lunghe → `timeout=<secondi>` come kwarg (default JSPyBridge = 10s).
- `collectBlock.collect` promise-only, **un blocco alla volta**.
- `recipesFor` è inventory-aware; per la definizione usa `recipesAll`.
- Esempi storici funzionanti: `/tmp/mtest.py` (catena piccone), `/tmp/ptest.py` (placeBlock).
