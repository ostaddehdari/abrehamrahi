import asyncio
import time

import aiosqlite
import pytest

from app.db import Database

from app.security import (
    hash_password,
    normalize_domain,
    normalize_phone,
    sign_request,
    verify_password,
    verify_request_signature,
)


def test_password_phone_domain_and_signature():
    password_hash = hash_password("A-secure-password-123")
    assert verify_password(password_hash, "A-secure-password-123")
    assert not verify_password(password_hash, "wrong-password")
    assert normalize_phone("+98 912 345 6789") == "9123456789"
    assert normalize_domain("https://Example.COM/") == "example.com"
    timestamp = str(int(time.time()))
    body = b'{"phone":"09123456789"}'
    signature = sign_request("secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", body)
    assert verify_request_signature(
        "secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", body, signature
    )
    assert not verify_request_signature(
        "secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", b"changed", signature
    )


@pytest.mark.asyncio
async def test_parallel_database_migration_is_serialized(tmp_path):
    database_path = tmp_path / "legacy.sqlite3"
    async with aiosqlite.connect(database_path) as conn:
        await conn.execute(
            """CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                encrypted_access_token TEXT,
                encrypted_refresh_token TEXT,
                upstream_token_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.commit()

    await asyncio.gather(
        Database(database_path).initialize(),
        Database(database_path).initialize(),
    )

    async with aiosqlite.connect(database_path) as conn:
        columns = {
            row[1]
            for row in await (await conn.execute("PRAGMA table_info(users)")).fetchall()
        }
    assert {
        "display_name",
        "upstream_password_set",
        "password_sync_error",
        "last_login_at",
    }.issubset(columns)

