from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..db import Database
from ..dependencies import get_db
from ..security import create_testpage_cookie, verify_testpage_cookie
from .admin import require_admin

router = APIRouter(tags=["برگه آزمایش"])
PAGE = Path(__file__).resolve().parent.parent / "testpage.html"
ASSETS = {
    "testpage.css": (PAGE.with_name("testpage.css"), "text/css; charset=utf-8"),
    "testpage.js": (PAGE.with_name("testpage.js"), "text/javascript; charset=utf-8"),
}


class AccountUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


def require_testpage_admin(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    if not verify_testpage_cookie(
        settings.admin_password, request.cookies.get("abr_testpage_admin")
    ):
        raise HTTPException(401, "نشست مدیریت صفحه آزمایش منقضی شده است")


@router.get("/testpage", include_in_schema=False)
@router.get("/testpage/", include_in_schema=False)
async def test_page(
    _admin: None = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    response = FileResponse(
        PAGE,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            ),
        },
    )
    response.set_cookie(
        "abr_testpage_admin",
        create_testpage_cookie(settings.admin_password),
        max_age=28800,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=settings.root_path or "/",
    )
    return response


@router.get("/testpage/assets/{filename}", include_in_schema=False)
async def testpage_asset(filename: str):
    asset = ASSETS.get(filename)
    if not asset:
        raise HTTPException(404, "فایل رابط پیدا نشد")
    return FileResponse(
        asset[0],
        media_type=asset[1],
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/testpage/api/accounts")
async def list_accounts(
    _admin: None = Depends(require_testpage_admin),
    db: Database = Depends(get_db),
):
    now = int(time.time())
    rows = await db.fetchall(
        """SELECT u.id,u.phone,u.display_name,u.upstream_password_set,
                  u.password_sync_error,u.last_login_at,u.created_at,u.updated_at,
                  CASE WHEN u.encrypted_refresh_token IS NOT NULL OR
                                 u.encrypted_access_token IS NOT NULL THEN 1 ELSE 0 END AS connected,
                  (SELECT COUNT(*) FROM sessions s
                   WHERE s.user_id=u.id AND s.expires_at>?) AS active_sessions
           FROM users u ORDER BY COALESCE(u.last_login_at,u.created_at) DESC,u.id DESC""",
        (now,),
    )
    return {"accounts": rows}


@router.patch("/testpage/api/accounts/{user_id}")
async def update_account(
    user_id: int,
    payload: AccountUpdate,
    _admin: None = Depends(require_testpage_admin),
    db: Database = Depends(get_db),
):
    user = await db.fetchone("SELECT id FROM users WHERE id=?", (user_id,))
    if not user:
        raise HTTPException(404, "حساب پیدا نشد")
    await db.execute(
        "UPDATE users SET display_name=?,updated_at=? WHERE id=?",
        (payload.display_name.strip(), int(time.time()), user_id),
    )
    return {"ok": True}


@router.post("/testpage/api/accounts/{user_id}/logout")
async def clear_account_sessions(
    user_id: int,
    _admin: None = Depends(require_testpage_admin),
    db: Database = Depends(get_db),
):
    await db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return {"ok": True}


@router.delete("/testpage/api/accounts/{user_id}")
async def delete_local_account(
    user_id: int,
    _admin: None = Depends(require_testpage_admin),
    db: Database = Depends(get_db),
):
    user = await db.fetchone("SELECT id FROM users WHERE id=?", (user_id,))
    if not user:
        raise HTTPException(404, "حساب پیدا نشد")
    await db.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"ok": True, "scope": "local_gateway_only"}
