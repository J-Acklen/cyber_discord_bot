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

CREATE TABLE IF NOT EXISTS rollcalls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    required_role_id INTEGER,
    created_by INTEGER NOT NULL,
    is_open INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rollcall_responses (
    rollcall_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    responded_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (rollcall_id, user_id)
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    added_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pwncollege_links (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    verify_code TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    role_granted INTEGER NOT NULL DEFAULT 0,
    linked_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, user_id)
);
"""


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn
