from __future__ import annotations

import html
import secrets
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..config import Settings, get_settings
from ..db import Database
from ..dependencies import get_crypto, get_db
from ..security import Crypto, create_random_token, hash_secret, normalize_domain

router = APIRouter(prefix="/admin", tags=["مدیریت توکن سایت"])
basic = HTTPBasic()


def require_admin(
    credentials: HTTPBasicCredentials = Depends(basic),
    settings: Settings = Depends(get_settings),
) -> None:
    valid_user = secrets.compare_digest(credentials.username.encode(), settings.admin_username.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز مدیریت درست نیست",
            headers={"WWW-Authenticate": "Basic"},
        )


def page(rows: list[dict], created: dict | None = None) -> str:
    items = "".join(
        f"<tr><td>{row['id']}</td><td>{html.escape(row['name'])}</td>"
        f"<td dir='ltr'>{html.escape(row['domain'])}</td>"
        f"<td>{'فعال' if row['active'] else 'غیرفعال'}</td>"
        f"<td><button onclick='revoke({row['id']})'>لغو</button></td></tr>"
        for row in rows
    )
    reveal = ""
    if created:
        reveal = f"""
        <section class="secret"><h2>این اطلاعات فقط همین یک بار نمایش داده می‌شود</h2>
        <label>توکن سایت</label><code>{html.escape(created['client_token'])}</code>
        <label>کلید امضا</label><code>{html.escape(created['signing_secret'])}</code>
        <p>دامنه: <b dir="ltr">{html.escape(created['domain'])}</b></p></section>"""
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>توکن‌های اتصال</title>
    <style>body{{font-family:Tahoma,sans-serif;max-width:950px;margin:35px auto;padding:0 16px;background:#f5f7fb;color:#18304b}}section{{background:white;padding:22px;border-radius:14px;margin:16px 0;box-shadow:0 2px 14px #dbe2ea}}input,button{{font:inherit;padding:10px;border:1px solid #ccd6e2;border-radius:8px;margin:4px}}button{{background:#1769aa;color:white;cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e8edf3;text-align:right}}code{{display:block;direction:ltr;white-space:pre-wrap;word-break:break-all;background:#eef3f8;padding:12px;margin:7px 0;border-radius:8px}}.secret{{border:2px solid #e09a20}}</style></head><body>
    <h1>توکن اتصال دامنه به ابرهمراهی</h1><p>برای هر سایت یک توکن جدا بسازید. کلید امضا را فقط در بک‌اند همان سایت نگه دارید.</p>
    {reveal}<section><h2>ایجاد توکن</h2><form method="post"><input name="name" placeholder="نام پروژه" required maxlength="100"><input name="domain" dir="ltr" placeholder="example.com" required maxlength="253"><button>ایجاد توکن</button></form></section>
    <section><h2>توکن‌های موجود</h2><table><thead><tr><th>شناسه</th><th>نام</th><th>دامنه</th><th>وضعیت</th><th></th></tr></thead><tbody>{items}</tbody></table></section>
    <script>async function revoke(id){{if(!confirm('این توکن غیرفعال شود؟'))return;let base=location.pathname.replace(/\\/$/,'');let r=await fetch(base+'/'+id+'/revoke',{{method:'POST'}});if(r.ok)location.reload();else alert('لغو توکن انجام نشد')}};</script>
    </body></html>"""


@router.get("/tokens", response_class=HTMLResponse)
async def token_page(
    _admin: None = Depends(require_admin),
    db: Database = Depends(get_db),
):
    rows = await db.fetchall("SELECT id,name,domain,active,created_at,last_used_at FROM api_clients ORDER BY id DESC")
    return page(rows)


@router.post("/tokens", response_class=HTMLResponse)
async def create_token(
    name: str = Form(..., min_length=1, max_length=100),
    domain: str = Form(..., min_length=3, max_length=253),
    _admin: None = Depends(require_admin),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
):
    try:
        normalized = normalize_domain(domain)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    client_token = create_random_token("abrc_")
    signing_secret = create_random_token("abrsig_")
    await db.execute(
        "INSERT INTO api_clients(name,domain,token_hash,encrypted_signing_secret,active,created_at) VALUES(?,?,?,?,1,?)",
        (name.strip(), normalized, hash_secret(client_token), crypto.encrypt(signing_secret), int(time.time())),
    )
    rows = await db.fetchall("SELECT id,name,domain,active,created_at,last_used_at FROM api_clients ORDER BY id DESC")
    return page(rows, {"client_token": client_token, "signing_secret": signing_secret, "domain": normalized})


@router.post("/tokens/{client_id}/revoke")
async def revoke_token(
    client_id: int,
    _admin: None = Depends(require_admin),
    db: Database = Depends(get_db),
):
    await db.execute("UPDATE api_clients SET active=0 WHERE id=?", (client_id,))
    return {"ok": True}

