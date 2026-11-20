from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from ..db import Database
from ..dependencies import get_crypto, get_db, get_upstream
from ..downloads import resolve_download_url
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
    download_url = await resolve_download_url(
        asset, asset["object_id"], db, crypto, upstream
    )
    response = RedirectResponse(download_url, status_code=302)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = f'inline; filename="{asset["name"].replace(chr(34), "")}"'
    return response

