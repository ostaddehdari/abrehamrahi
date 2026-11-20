from __future__ import annotations

import math
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

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
from ..upstream import UpstreamClient, UpstreamError

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


def _normalize_etag(value: str) -> str:
    """Match the Android client before complete-upload.

    S3-compatible storage usually returns ETag as a quoted header.  The
    official client removes escaping and surrounding quotes before it builds
    the `Parts(ETag, PartNumber)` payload expected by Abrehamrahi.
    """
    cleaned = value.strip().replace("\\", "")
    if cleaned.startswith('W/"') and cleaned.endswith('"'):
        cleaned = cleaned[3:-1]
    return cleaned.strip('"')


def _is_folder(item: dict[str, Any]) -> bool:
    for key in ("is_folder", "is_dir", "folder"):
        value = item.get(key)
        if isinstance(value, bool):
            return value
        if value in (0, 1, "0", "1"):
            return str(value) == "1"
    if item.get("is_file") is True:
        return False
    kind = " ".join(
        str(item.get(key, "")).lower()
        for key in ("type", "object_type", "obj_type", "kind", "mime_type")
    )
    return "folder" in kind or "directory" in kind or kind.strip() == "dir"


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        if not isinstance(value, str):
            return None
    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*(b|byte|bytes|kb|kib|mb|mib|gb|gib|tb|tib)\s*",
        value.lower().replace(",", ""),
    )
    if not match:
        return None
    factors = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024**2,
        "mib": 1024**2,
        "gb": 1024**3,
        "gib": 1024**3,
        "tb": 1024**4,
        "tib": 1024**4,
    }
    return int(float(match.group(1)) * factors[match.group(2)])


def _find_quota_number(data: Any, names: tuple[str, ...]) -> int | None:
    wanted = {name.lower().replace("-", "_") for name in names}
    if isinstance(data, dict):
        for key, value in data.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in wanted:
                parsed = _integer(value)
                if parsed is not None:
                    return parsed
        for value in data.values():
            found = _find_quota_number(value, names)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_quota_number(value, names)
            if found is not None:
                return found
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
            if not isinstance(item, dict) or item.get("id") is None or _is_folder(item):
                continue
            object_id = str(item["id"])
            if object_id not in cdn:
                registered = await _register_asset(
                    db,
                    settings,
                    user["id"],
                    object_id,
                    str(item.get("name") or item.get("title") or "file"),
                    str(item.get("parent") or item.get("parent_id") or "") or None,
                    item.get("mime_type") or item.get("content_type"),
                    _integer(item.get("size") or item.get("obj_size")),
                )
                cdn[object_id] = registered["cdn_url"]
            item["cdn_url"] = cdn[object_id]
    return result


@router.get("/quota")
async def get_quota(
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    result = await upstream_request_for_user(
        user, db, crypto, upstream, "GET", "/api/v3/rgw/get-quota/"
    )
    total = _find_quota_number(
        result,
        (
            "total",
            "quota",
            "total_space",
            "quota_size",
            "max_size",
            "capacity",
            "limit",
            "storage_limit",
            "hard_limit",
        ),
    )
    used = _find_quota_number(
        result,
        (
            "used",
            "usage",
            "used_space",
            "usage_size",
            "consumed",
            "occupied",
            "current_usage",
            "storage_used",
        ),
    )
    remaining = _find_quota_number(
        result, ("remaining", "remaining_space", "free", "free_space", "available")
    )
    if remaining is None and total is not None and used is not None:
        remaining = max(0, total - used)
    if total is None and used is not None and remaining is not None:
        total = used + remaining
    return {"total": total, "used": used, "remaining": remaining, "raw": result}


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


@router.delete("/files/{object_id}")
async def delete_file(
    object_id: str,
    permanent: bool = Query(False),
    _client: dict = Depends(require_api_client),
    user: dict = Depends(require_user),
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    if permanent:
        upstream_result = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "DELETE",
            "/api/v3/rgw/delete-object/" + quote(object_id, safe="") + "/",
        )
    else:
        upstream_result = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "POST",
            "/api/v2/rgw/trash-objects/",
            json={"obj_ids": [object_id]},
        )
    await db.execute(
        "DELETE FROM assets WHERE user_id=? AND object_id=?", (user["id"], object_id)
    )
    return {"ok": True, "object_id": object_id, "permanent": permanent, "upstream": upstream_result}


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

    try:
        started = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "POST",
            "/api/v2/flat/start-upload/",
            json={"obj_size": size},
        )
    except UpstreamError as exc:
        raise UpstreamError(
            exc.status_code,
            "ابرهمراهی آغاز بارگذاری را نپذیرفت",
            exc.detail,
        ) from exc
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
            normalized_etag = _normalize_etag(etag)
            if not normalized_etag:
                raise HTTPException(502, f"ETag بخش {number} معتبر نیست")
            parts.append({"ETag": normalized_etag, "PartNumber": number})

    complete_payload = {
        "key": key,
        "name": filename,
        "parent": parent,
        "upload_id": upload_id,
        "parts": parts,
        "force_overwrite": force_overwrite,
        "is_hidden": is_hidden,
    }
    try:
        completed = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "POST",
            "/api/v2/flat/complete-upload/",
            json=complete_payload,
        )
    except UpstreamError as exc:
        try:
            await upstream_request_for_user(
                user,
                db,
                crypto,
                upstream,
                "POST",
                "/api/v2/flat/abort-upload/",
                json={"upload_id": upload_id, "key": key},
            )
        except UpstreamError:
            pass
        raise UpstreamError(
            exc.status_code,
            "ابرهمراهی تکمیل بارگذاری را نپذیرفت",
            exc.detail,
        ) from exc
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
