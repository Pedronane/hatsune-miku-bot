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
        c.execute(
            "CREATE TABLE IF NOT EXISTS chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER, "
            "role TEXT, content TEXT, ts INTEGER)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS miku_facts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, fact TEXT, ts INTEGER)"
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


def add_history(channel_id, role, content):
    with conn() as c:
        c.execute(
            "INSERT INTO chat_history (channel_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (channel_id, role, content, int(time.time())),
        )
        c.execute(
            "DELETE FROM chat_history WHERE channel_id = ? AND id NOT IN "
            "(SELECT id FROM chat_history WHERE channel_id = ? ORDER BY id DESC LIMIT 40)",
            (channel_id, channel_id),
        )


def get_history(channel_id, limit=8):
    with conn() as c:
        rows = c.execute(
            "SELECT role, content FROM chat_history WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
            (channel_id, limit),
        ).fetchall()
        return list(reversed(rows))


def add_fact(guild_id, fact):
    with conn() as c:
        c.execute(
            "INSERT INTO miku_facts (guild_id, fact, ts) VALUES (?, ?, ?)",
            (guild_id, fact, int(time.time())),
        )


def get_facts(guild_id, limit=40):
    with conn() as c:
        return c.execute(
            "SELECT fact FROM miku_facts WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()


def clear_facts(guild_id):
    with conn() as c:
        cur = c.execute("DELETE FROM miku_facts WHERE guild_id = ?", (guild_id,))
        return cur.rowcount
