from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..config import Settings, get_settings
from ..security import create_testpage_cookie
from .admin import require_admin

router = APIRouter(tags=["برگه آزمایش"])
PAGE = Path(__file__).resolve().parent.parent / "testpage.html"


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
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
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
