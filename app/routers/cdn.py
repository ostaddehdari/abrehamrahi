from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from ..db import Database
from ..dependencies import get_crypto, get_db, get_upstream, upstream_request_for_user
from ..security import Crypto
from ..upstream import UpstreamClient

router = APIRouter(tags=["CDN"])


@router.get("/cdn/{public_id}", include_in_schema=True)
async def stable_download(
    public_id: str,
    db: Database = Depends(get_db),
    crypto: Crypto = Depends(get_crypto),
    upstream: UpstreamClient = Depends(get_upstream),
):
    asset = await db.fetchone(
        """SELECT a.*,u.phone,u.encrypted_access_token,u.encrypted_refresh_token,u.upstream_token_id
           FROM assets a JOIN users u ON u.id=a.user_id WHERE a.public_id=?""",
        (public_id,),
    )
    if not asset:
        raise HTTPException(404, "فایل پیدا نشد")
    result = await upstream_request_for_user(
        asset,
        db,
        crypto,
        upstream,
        "GET",
        "/api/v1/flat/get-download-url/" + quote(asset["object_id"], safe="") + "/",
    )
    if not isinstance(result, dict) or not result.get("download_url"):
        raise HTTPException(502, "لینک دانلود از ابرهمراهی دریافت نشد")
    response = RedirectResponse(result["download_url"], status_code=302)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = f'inline; filename="{asset["name"].replace(chr(34), "")}"'
    return response

