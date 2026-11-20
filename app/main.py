from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .config import get_settings, validate_settings
from .db import Database
from .routers import admin, auth, cdn, files, testpage
from .security import Crypto, origin_domain
from .upstream import UpstreamClient, UpstreamError

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("abrehamrahi")


def _public_upstream_detail(value, depth: int = 0):
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:30]:
            normalized = str(key).lower().replace("-", "_")
            if any(
                secret in normalized
                for secret in ("password", "authorization", "cookie", "access_token", "refresh_token", "secret")
            ):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = _public_upstream_detail(item, depth + 1)
        return result
    if isinstance(value, list):
        return [_public_upstream_detail(item, depth + 1) for item in value[:30]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:1000] if isinstance(value, str) else value
    return str(value)[:1000]


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_settings(settings)
    app.state.db = Database(settings.database_path)
    await app.state.db.initialize()
    await app.state.db.cleanup()
    app.state.crypto = Crypto(settings.encryption_key)
    app.state.upstream = UpstreamClient(settings.api_origin, settings.upstream_timeout_seconds)
    yield


app = FastAPI(
    title="درگاه API ابرهمراهی",
    description="درگاه بک‌اند برای ورود، فایل، پوشه، بارگذاری و لینک پایدار دامنه‌محور",
    version="1.2.3",
    root_path=settings.root_path,
    lifespan=lifespan,
)


@app.middleware("http")
async def domain_cors(request: Request, call_next):
    origin = request.headers.get("origin")
    domain = origin_domain(origin)
    allowed = False
    if domain and hasattr(request.app.state, "db"):
        allowed = bool(
            await request.app.state.db.fetchone(
                "SELECT id FROM api_clients WHERE domain=? AND active=1", (domain,)
            )
        )
    if request.method == "OPTIONS" and origin:
        if not allowed:
            return JSONResponse({"detail": "دامنه مجاز نیست"}, status_code=403)
        response: Response = Response(status_code=204)
    else:
        response = await call_next(request)
    if origin and allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization,Content-Type,X-ABR-Client-Token,X-ABR-Domain,X-ABR-Timestamp,X-ABR-Signature,X-ABR-Content-SHA256"
        )
        response.headers["Access-Control-Max-Age"] = "600"
    return response


@app.exception_handler(UpstreamError)
async def upstream_error_handler(_request: Request, exc: UpstreamError):
    detail = _public_upstream_detail(exc.detail)
    logger.warning(
        "Upstream request failed with status %s: %s detail=%r",
        exc.status_code,
        exc.message,
        detail,
    )
    outward = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        {
            "detail": exc.message,
            "upstream_status": exc.status_code,
            "upstream_detail": detail,
        },
        status_code=outward,
    )


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(settings.root_path + "/docs" if settings.root_path else "/docs")


@app.get("/health", tags=["سامانه"])
async def health():
    return {"status": "ok", "version": app.version}


app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(cdn.router)
app.include_router(testpage.router)
