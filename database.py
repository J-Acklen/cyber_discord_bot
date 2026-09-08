"""Shared SQLite access for the bot. One connection pool object, created in bot.py
and attached to bot.db, so every cog reads/writes the same database file."""

import aiosqlite

DB_PATH = "data/bot.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS role_links (
    guild_id INTEGER NOT NULL,
    trigger_role_id INTEGER NOT NULL,
    linked_role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, trigger_role_id, linked_role_id)
);

CREATE TABLE IF NOT EXISTS ctf_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    points INTEGER NOT NULL,
    flag TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS ctf_solves (
    challenge_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    solved_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (challenge_id, user_id)
);
"""


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn
