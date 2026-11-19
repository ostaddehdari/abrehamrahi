from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from .admin import require_admin

router = APIRouter(tags=["برگه آزمایش"])
PAGE = Path(__file__).resolve().parent.parent / "testpage.html"


@router.get("/testpage", include_in_schema=False)
@router.get("/testpage/", include_in_schema=False)
async def test_page(_admin: None = Depends(require_admin)):
    return FileResponse(
        PAGE,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            ),
        },
    )
