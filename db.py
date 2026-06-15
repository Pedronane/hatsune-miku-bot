import sqlite3
import time
from pathlib import Path

DB = Path(__file__).parent / "data.db"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS xp ("
            "guild_id INTEGER, user_id INTEGER, xp INTEGER DEFAULT 0, "
            "PRIMARY KEY (guild_id, user_id))"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS warns ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, "
            "mod_id INTEGER, reason TEXT, ts INTEGER)"
        )


def add_xp(guild_id, user_id, amount):
    with conn() as c:
        c.execute(
            "INSERT INTO xp (guild_id, user_id, xp) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
            (guild_id, user_id, amount, amount),
        )


def get_xp(guild_id, user_id):
    with conn() as c:
        row = c.execute(
            "SELECT xp FROM xp WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        ).fetchone()
        return row["xp"] if row else 0


def top_xp(guild_id, limit=10):
    with conn() as c:
        return c.execute(
            "SELECT user_id, xp FROM xp WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()


def add_warn(guild_id, user_id, mod_id, reason):
    with conn() as c:
        c.execute(
            "INSERT INTO warns (guild_id, user_id, mod_id, reason, ts) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, reason, int(time.time())),
        )


def get_warns(guild_id, user_id):
    with conn() as c:
        return c.execute(
            "SELECT mod_id, reason, ts FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY ts DESC",
            (guild_id, user_id),
        ).fetchall()
