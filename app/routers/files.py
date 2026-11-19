from __future__ import annotations

import math
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..config import Settings, get_settings
from ..db import Database
from ..dependencies import (
    get_crypto,
    get_db,
    get_upstream,
    require_api_client,
    require_user,
    upstream_request_for_user,
)
from ..models import FolderCreate, RegisterCdn
from ..security import Crypto
from ..upstream import UpstreamClient

router = APIRouter(prefix="/v1", tags=["فایل و پوشه"])


def _object_id(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("id") is not None:
        return str(result["id"])
    for key in ("object", "result", "data"):
        value = result.get(key)
        if isinstance(value, dict) and value.get("id") is not None:
            return str(value["id"])
    return None


def _signed_url(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("url") or entry.get("signed_url") or entry.get("signedUrl")
    return None


async def _register_asset(
    db: Database,
    settings: Settings,
    user_id: int,
    object_id: str,
    name: str,
    parent_id: str | None,
    mime_type: str | None,
    size: int | None,
) -> dict[str, Any]:
    existing = await db.fetchone(
        "SELECT * FROM assets WHERE user_id=? AND object_id=?", (user_id, object_id)
    )
    public_id = existing["public_id"] if existing else uuid.uuid4().hex
    now = int(time.time())
    await db.execute(
        """INSERT INTO assets(public_id,user_id,object_id,parent_id,name,mime_type,size,created_at)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id,object_id) DO UPDATE SET
           parent_id=excluded.parent_id,name=excluded.name,mime_type=excluded.mime_type,size=excluded.size""",
        (public_id, user_id, object_id, parent_id, name, mime_type, size, now),
    )
    return {
        "public_id": public_id,
        "cdn_url": f"{settings.public_base_url}/cdn/{public_id}",
    }


@router.get("/files")
async def list_files(
    parent: str | None = None,
    offset: int = 0,
    limit: int = 100,
    recursive: bool = False,
    is_favorite: bool | None = None,
    is_trash: bool | None = None,
    is_hidden: bool | None = None,
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(400, "offset یا limit معتبر نیست")
    params: dict[str, Any] = {"offset": offset, "limit": limit, "recursive": str(recursive).lower()}
    if parent:
        params["parent"] = parent
    for key, value in (("is_favorite", is_favorite), ("is_trash", is_trash), ("is_hidden", is_hidden)):
        if value is not None:
            params[key] = str(value).lower()
    result = await upstream_request_for_user(
        user, db, crypto, upstream, "GET", "/api/v2/flat/list-objects/", params=params
    )
    if isinstance(result, dict) and isinstance(result.get("results"), list):
        assets = await db.fetchall("SELECT object_id,public_id FROM assets WHERE user_id=?", (user["id"],))
        cdn = {row["object_id"]: f"{settings.public_base_url}/cdn/{row['public_id']}" for row in assets}
        for item in result["results"]:
            if isinstance(item, dict) and str(item.get("id")) in cdn:
                item["cdn_url"] = cdn[str(item["id"])]
    return result


@router.post("/folders")
async def create_folder(
    payload: FolderCreate,
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    return await upstream_request_for_user(
        user,
        db,
        crypto,
        upstream,
        "POST",
        "/api/v2/flat/create-folder/",
        json={"name": payload.name, "parent": payload.parent or ""},
    )


@router.get("/files/{object_id}/download-link")
async def get_download_link(
    object_id: str,
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    result = await upstream_request_for_user(
        user,
        db,
        crypto,
        upstream,
        "GET",
        "/api/v1/flat/get-download-url/" + quote(object_id, safe="") + "/",
    )
    if not isinstance(result, dict) or not result.get("download_url"):
        raise HTTPException(502, "لینک دانلود در پاسخ ابرهمراهی موجود نیست")
    return {"object_id": object_id, "download_url": result["download_url"]}


@router.post("/files/{object_id}/register-cdn")
async def register_existing_file(
    object_id: str,
    payload: RegisterCdn,
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return await _register_asset(
        db, settings, user["id"], object_id, payload.name, payload.parent_id, payload.mime_type, payload.size
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    parent: str = Form(""),
    force_overwrite: bool = Form(False),
    is_hidden: bool = Form(False),
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size <= 0 or size > settings.max_upload_bytes:
        raise HTTPException(400, "اندازه فایل صفر یا بیشتر از سقف مجاز است")
    filename = Path(file.filename or "file.bin").name

    started = await upstream_request_for_user(
        user, db, crypto, upstream, "POST", "/api/v2/flat/start-upload/", json={"obj_size": size}
    )
    if not isinstance(started, dict):
        raise HTTPException(502, "پاسخ آغاز بارگذاری معتبر نیست")
    upload_id = started.get("upload_id")
    key = started.get("key")
    links = started.get("signed_urls")
    chunk_size = started.get("chunk_size")
    if not upload_id or not key or not isinstance(links, list) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise HTTPException(502, "پارامترهای بارگذاری در پاسخ ابرهمراهی کامل نیست")
    if len(links) != math.ceil(size / chunk_size):
        raise HTTPException(502, "تعداد لینک‌های امضاشده با اندازه فایل برابر نیست")

    parts: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=settings.signed_url_timeout_seconds, follow_redirects=False) as client:
        for number, entry in enumerate(links, 1):
            signed = _signed_url(entry)
            if not signed or urlparse(signed).scheme != "https":
                raise HTTPException(502, "یکی از لینک‌های امضاشده معتبر نیست")
            chunk = await file.read(chunk_size)
            try:
                response = await client.put(signed, content=chunk, headers={"Content-Length": str(len(chunk))})
            except httpx.RequestError as exc:
                raise HTTPException(502, f"ارسال بخش {number} فایل ناموفق بود") from exc
            etag = response.headers.get("ETag")
            if not response.is_success or not etag:
                raise HTTPException(502, f"ابر ذخیره‌سازی بخش {number} را تأیید نکرد")
            parts.append({"ETag": etag, "PartNumber": number})

    completed = await upstream_request_for_user(
        user,
        db,
        crypto,
        upstream,
        "POST",
        "/api/v2/flat/complete-upload/",
        json={
            "key": key,
            "name": filename,
            "parent": parent,
            "upload_id": upload_id,
            "parts": parts,
            "force_overwrite": force_overwrite,
            "version_group": None,
            "is_hidden": is_hidden,
        },
    )
    object_id = _object_id(completed)
    if not object_id:
        raise HTTPException(502, "شناسه فایل تکمیل‌شده در پاسخ موجود نیست")
    registered = await _register_asset(
        db, settings, user["id"], object_id, filename, parent or None, file.content_type, size
    )
    download = await upstream_request_for_user(
        user,
        db,
        crypto,
        upstream,
        "GET",
        "/api/v1/flat/get-download-url/" + quote(object_id, safe="") + "/",
    )
    return {
        "object": completed,
        "object_id": object_id,
        "name": filename,
        "size": size,
        "download_url": download.get("download_url") if isinstance(download, dict) else None,
        **registered,
    }
