from __future__ import annotations

from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ..config import Settings, get_settings
from ..db import Database
from ..dependencies import access_token_for_user, get_crypto, get_db, get_upstream
from ..downloads import resolve_download_url
from ..security import Crypto
from ..upstream import UpstreamClient, UpstreamError

router = APIRouter(tags=["CDN"])
AsyncHTTPClient = httpx.AsyncClient


@router.get("/cdn/{public_id}", include_in_schema=True)
async def stable_download(
    public_id: str,
    request: Request,
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
    settings: Settings = Depends(get_settings),
):
    asset = await db.fetchone(
        """SELECT a.*,u.phone,u.encrypted_access_token,u.encrypted_refresh_token,u.upstream_token_id
           FROM assets a JOIN users u ON u.id=a.user_id WHERE a.public_id=?""",
        (public_id,),
    )
    if not asset:
        raise HTTPException(404, "فایل پیدا نشد")
    download_url = await resolve_download_url(
        asset, asset["object_id"], db, crypto, upstream
    )

    # Do not redirect the browser to the upstream URL. Some Abrehamrahi URLs
    # require the account bearer token and otherwise respond with 403. Proxying
    # also keeps the stable CDN URL unchanged for the caller.
    headers = {
        "Accept": "*/*",
        "User-Agent": "AbrehamrahiWebGateway/1.0",
    }
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    if urlparse(download_url).netloc == urlparse(upstream.origin).netloc:
        access = await access_token_for_user(asset, db, crypto, upstream)
        headers["Authorization"] = f"Bearer {access}"

    client = AsyncHTTPClient(
        timeout=settings.signed_url_timeout_seconds,
        follow_redirects=True,
    )
    try:
        upstream_response = await client.send(
            client.build_request("GET", download_url, headers=headers), stream=True
        )
    except httpx.RequestError as exc:
        await client.aclose()
        raise UpstreamError(502, "دریافت فایل از فضای ابری برقرار نشد") from exc

    if upstream_response.status_code >= 400:
        body = (await upstream_response.aread()).decode("utf-8", "replace")[:1000]
        status = upstream_response.status_code
        await upstream_response.aclose()
        await client.aclose()
        raise UpstreamError(
            status,
            "فضای ذخیره‌سازی دانلود فایل را نپذیرفت",
            body,
        )

    async def close_stream() -> None:
        await upstream_response.aclose()
        await client.aclose()

    passthrough = {}
    for name in (
        "content-type",
        "content-length",
        "content-range",
        "accept-ranges",
        "etag",
        "last-modified",
        "content-encoding",
    ):
        value = upstream_response.headers.get(name)
        if value:
            passthrough[name] = value
    filename = quote(str(asset["name"]), safe="")
    passthrough["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
    passthrough["Cache-Control"] = "private, no-store"
    return StreamingResponse(
        upstream_response.aiter_raw(),
        status_code=upstream_response.status_code,
        headers=passthrough,
        background=BackgroundTask(close_stream),
    )

