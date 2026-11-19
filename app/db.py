from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    upstream_token_id TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    user_agent TEXT,
    ip_address TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS api_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    encrypted_signing_secret TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    last_used_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_clients_domain ON api_clients(domain);

CREATE TABLE IF NOT EXISTS otp_challenges (
    id TEXT PRIMARY KEY,
    api_client_id INTEGER NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    consumed_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_otp_phone ON otp_challenges(phone);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    parent_id TEXT,
    name TEXT NOT NULL,
    mime_type TEXT,
    size INTEGER,
    created_at INTEGER NOT NULL,
    UNIQUE(user_id, object_id)
);
CREATE INDEX IF NOT EXISTS idx_assets_object ON assets(object_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        async with self.connection() as conn:
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with self.connection() as conn:
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.lastrowid

    async def cleanup(self) -> None:
        now = int(time.time())
        async with self.connection() as conn:
            await conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            await conn.execute("DELETE FROM otp_challenges WHERE expires_at < ?", (now,))
            await conn.commit()

