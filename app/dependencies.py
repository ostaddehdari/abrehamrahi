from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings
from .db import Database
from .security import (
    Crypto,
    hash_secret,
    origin_domain,
    verify_prehashed_request_signature,
    verify_testpage_cookie,
)
from .upstream import UpstreamClient, UpstreamError

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_crypto(request: Request) -> Crypto:
    return request.app.state.crypto


def get_upstream(request: Request) -> UpstreamClient:
    return request.app.state.upstream


async def require_api_client(
    request: Request,
    x_abr_client_token: str | None = Header(default=None),
    x_abr_domain: str | None = Header(default=None),
    x_abr_timestamp: str | None = Header(default=None),
    x_abr_signature: str | None = Header(default=None),
    x_abr_content_sha256: str | None = Header(default=None),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if not x_abr_client_token:
        raise HTTPException(401, "X-ABR-Client-Token لازم است")
    client = await db.fetchone(
        "SELECT * FROM api_clients WHERE token_hash=? AND active=1",
        (hash_secret(x_abr_client_token),),
    )
    if not client:
        raise HTTPException(401, "توکن سایت معتبر نیست")

    origin = origin_domain(request.headers.get("origin"))
    if origin:
        if origin != client["domain"]:
            raise HTTPException(403, "این توکن به دامنه دیگری تعلق دارد")
    elif verify_testpage_cookie(
        settings.admin_password, request.cookies.get("abr_testpage_admin")
    ):
        pass
    else:
        if x_abr_domain != client["domain"]:
            raise HTTPException(403, "دامنه درخواست با توکن مطابقت ندارد")
        if not x_abr_timestamp or not x_abr_signature or not x_abr_content_sha256:
            raise HTTPException(401, "امضای درخواست بک‌اند لازم است")
        secret = crypto.decrypt(client["encrypted_signing_secret"])
        scope_path = request.scope.get("path", request.url.path)
        root_path = request.scope.get("root_path", "").rstrip("/")
        candidate_paths = {request.url.path, scope_path, root_path + scope_path}
        if not secret or not any(
            verify_prehashed_request_signature(
                secret, x_abr_timestamp, request.method, path, x_abr_content_sha256, x_abr_signature
            )
            for path in candidate_paths
        ):
            raise HTTPException(401, "امضای درخواست معتبر نیست یا منقضی شده است")

    await db.execute("UPDATE api_clients SET last_used_at=? WHERE id=?", (int(time.time()), client["id"]))
    return client


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "نشست کاربر لازم است")
    session = await db.fetchone(
        """SELECT u.*, s.expires_at FROM sessions s
           JOIN users u ON u.id=s.user_id
           WHERE s.token_hash=?""",
        (hash_secret(credentials.credentials),),
    )
    if not session or session["expires_at"] < int(time.time()):
        raise HTTPException(401, "نشست کاربر نامعتبر یا منقضی است")
    return session


async def create_session(db: Database, user_id: int, ttl: int, request: Request) -> str:
    token = "abrs_" + secrets.token_urlsafe(36)
    now = int(time.time())
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    await db.execute(
        "INSERT INTO sessions(token_hash,user_id,expires_at,created_at,user_agent,ip_address) VALUES(?,?,?,?,?,?)",
        (
            hash_secret(token), user_id, now + ttl, now,
            request.headers.get("user-agent", "")[:500], forwarded or (request.client.host if request.client else None),
        ),
    )
    return token


async def save_upstream_tokens(db: Database, crypto: Crypto, phone: str, data: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    existing = await db.fetchone("SELECT * FROM users WHERE phone=?", (phone,))
    access = crypto.encrypt(data.get("access"))
    refresh = crypto.encrypt(data.get("refresh"))
    token_id = str(data.get("token_id")) if data.get("token_id") is not None else None
    if existing:
        await db.execute(
            """UPDATE users SET encrypted_access_token=?, encrypted_refresh_token=?,
               upstream_token_id=?, updated_at=? WHERE id=?""",
            (access, refresh or existing["encrypted_refresh_token"], token_id, now, existing["id"]),
        )
        return (await db.fetchone("SELECT * FROM users WHERE id=?", (existing["id"],))) or existing
    user_id = await db.execute(
        """INSERT INTO users(phone,encrypted_access_token,encrypted_refresh_token,
           upstream_token_id,created_at,updated_at) VALUES(?,?,?,?,?,?)""",
        (phone, access, refresh, token_id, now, now),
    )
    return (await db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))) or {"id": user_id, "phone": phone}


async def access_token_for_user(
    user: dict[str, Any], db: Database, crypto: Crypto, upstream: UpstreamClient
) -> str:
    refresh = crypto.decrypt(user.get("encrypted_refresh_token"))
    access = crypto.decrypt(user.get("encrypted_access_token"))
    if refresh:
        try:
            tokens = await upstream.refresh(refresh)
            updated = await save_upstream_tokens(db, crypto, user["phone"], tokens)
            return crypto.decrypt(updated["encrypted_access_token"]) or tokens["access"]
        except UpstreamError as exc:
            if exc.status_code not in (400, 401, 403):
                raise
    if access:
        return access
    raise HTTPException(401, "برای اتصال دوباره به ابرهمراهی وارد شوید")


async def upstream_request_for_user(
    user: dict[str, Any],
    db: Database,
    crypto: Crypto,
    upstream: UpstreamClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> Any:
    access = crypto.decrypt(user.get("encrypted_access_token"))
    if access:
        try:
            return await upstream.request(method, path, access_token=access, **kwargs)
        except UpstreamError as exc:
            if exc.status_code not in (401, 403):
                raise
    access = await access_token_for_user(user, db, crypto, upstream)
    return await upstream.request(method, path, access_token=access, **kwargs)
