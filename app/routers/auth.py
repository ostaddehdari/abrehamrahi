from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from ..config import Settings, get_settings
from ..db import Database
from ..dependencies import (
    bearer,
    create_session,
    get_crypto,
    get_db,
    get_upstream,
    require_api_client,
    require_user,
    save_upstream_tokens,
)
from ..models import PasswordLogin, PasswordSetup, SmsRequest, SmsVerify
from ..security import Crypto, hash_password, hash_secret, verify_password
from ..upstream import UpstreamClient, UpstreamError

router = APIRouter(prefix="/v1/auth", tags=["احراز هویت"])


@router.get("/captcha")
async def captcha(
    _client: dict = Depends(require_api_client),
    upstream: UpstreamClient = Depends(get_upstream),
):
    return await upstream.request("GET", "/api/v1/captcha/get-captcha/")


@router.post("/sms/request")
async def request_sms(
    payload: SmsRequest,
    client: dict = Depends(require_api_client),
    db: Database = Depends(get_db),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    body = {
        "phone": payload.phone,
        "prefix": "+98",
        "request_type": payload.request_type,
    }
    if payload.captcha_id:
        body.update(
            captcha_id=payload.captcha_id,
            captcha_value=payload.captcha_value,
            captcha_provider=payload.captcha_provider,
        )
    response = await upstream.request("POST", "/api/v6/profile/auth/generate-code/", json=body)
    challenge_id = str(uuid.uuid4())
    now = int(time.time())
    await db.execute(
        "INSERT INTO otp_challenges(id,api_client_id,phone,created_at,expires_at) VALUES(?,?,?,?,?)",
        (challenge_id, client["id"], payload.phone, now, now + settings.otp_ttl_seconds),
    )
    return {
        "challenge_id": challenge_id,
        "expires_in": settings.otp_ttl_seconds,
        "upstream": response,
    }


async def _set_upstream_password(
    upstream: UpstreamClient,
    crypto: Crypto,
    user: dict,
    new_password: str,
    code: int | None,
) -> None:
    access = crypto.decrypt(user.get("encrypted_access_token"))
    refresh = crypto.decrypt(user.get("encrypted_refresh_token"))
    body: dict = {"new_password": new_password}
    if refresh:
        body["refresh"] = refresh
    if code is not None:
        body["code"] = code
    await upstream.request(
        "POST", "/api/v2/profile/auth/change-password/", access_token=access, json=body
    )


@router.post("/sms/verify")
async def verify_sms(
    payload: SmsVerify,
    request: Request,
    client: dict = Depends(require_api_client),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    challenge = await db.fetchone("SELECT * FROM otp_challenges WHERE id=?", (payload.challenge_id,))
    now = int(time.time())
    if (
        not challenge
        or challenge["api_client_id"] != client["id"]
        or challenge["expires_at"] < now
        or challenge["consumed_at"] is not None
    ):
        raise HTTPException(400, "درخواست پیامک نامعتبر یا منقضی است")

    login = await upstream.login(challenge["phone"], code=payload.code)
    user = await save_upstream_tokens(db, crypto, challenge["phone"], login)
    if payload.new_password:
        await _set_upstream_password(upstream, crypto, user, payload.new_password, payload.code)
        password_hash = hash_password(payload.new_password)
        await db.execute(
            "UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
            (password_hash, now, user["id"]),
        )
    await db.execute("UPDATE otp_challenges SET consumed_at=? WHERE id=?", (now, challenge["id"]))
    session_token = await create_session(db, user["id"], settings.session_ttl_seconds, request)
    return {
        "session_token": session_token,
        "token_type": "Bearer",
        "expires_in": settings.session_ttl_seconds,
        "phone": "+98" + challenge["phone"],
        "password_configured": bool(payload.new_password or user.get("password_hash")),
        "is_registered": login.get("is_registered"),
    }


@router.post("/password")
async def set_password(
    payload: PasswordSetup,
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    await _set_upstream_password(
        upstream, crypto, user, payload.new_password, payload.verification_code
    )
    await db.execute(
        "UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
        (hash_password(payload.new_password), int(time.time()), user["id"]),
    )
    return {"ok": True}


@router.post("/login")
async def password_login(
    payload: PasswordLogin,
    request: Request,
    _client: dict = Depends(require_api_client),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    user = await db.fetchone("SELECT * FROM users WHERE phone=?", (payload.phone,))
    if not user or not verify_password(user.get("password_hash"), payload.password):
        raise HTTPException(401, "شماره یا رمز عبور نادرست است")

    refresh = crypto.decrypt(user.get("encrypted_refresh_token"))
    try:
        login = await upstream.refresh(refresh) if refresh else await upstream.login(
            payload.phone, password=payload.password
        )
    except UpstreamError as exc:
        if refresh and exc.status_code in (400, 401, 403):
            login = await upstream.login(payload.phone, password=payload.password)
        else:
            raise
    user = await save_upstream_tokens(db, crypto, payload.phone, login)
    session_token = await create_session(db, user["id"], settings.session_ttl_seconds, request)
    return {
        "session_token": session_token,
        "token_type": "Bearer",
        "expires_in": settings.session_ttl_seconds,
    }


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    _user: dict = Depends(require_user),
    db: Database = Depends(get_db),
):
    if credentials:
        await db.execute("DELETE FROM sessions WHERE token_hash=?", (hash_secret(credentials.credentials),))
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(require_user), _client: dict = Depends(require_api_client)):
    return {"id": user["id"], "phone": "+98" + user["phone"]}
