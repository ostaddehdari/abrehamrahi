from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_origin: str
    root_path: str
    public_base_url: str
    database_path: Path
    encryption_key: str
    admin_username: str
    admin_password: str
    session_ttl_seconds: int
    otp_ttl_seconds: int
    max_upload_bytes: int
    upstream_timeout_seconds: float
    signed_url_timeout_seconds: float
    cookie_secure: bool
    log_level: str


@lru_cache
def get_settings() -> Settings:
    root_path = os.getenv("APP_ROOT_PATH", "").rstrip("/")
    public_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    return Settings(
        api_origin=os.getenv("ABR_API_ORIGIN", "https://abrehamrahi.ir").rstrip("/"),
        root_path=root_path,
        public_base_url=public_url,
        database_path=Path(os.getenv("DATABASE_PATH", "data/abrehamrahi.sqlite3")),
        encryption_key=os.getenv("ENCRYPTION_KEY", ""),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "2592000")),
        otp_ttl_seconds=int(os.getenv("OTP_TTL_SECONDS", "600")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "5368709120")),
        upstream_timeout_seconds=float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "60")),
        signed_url_timeout_seconds=float(os.getenv("SIGNED_URL_TIMEOUT_SECONDS", "300")),
        cookie_secure=_bool("COOKIE_SECURE", True),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def validate_settings(settings: Settings) -> None:
    if not settings.encryption_key or settings.encryption_key == "CHANGE_ME":
        raise RuntimeError("ENCRYPTION_KEY must be a valid Fernet key")
    if not settings.admin_password or settings.admin_password == "CHANGE_ME":
        raise RuntimeError("ADMIN_PASSWORD must be configured")
    if not settings.public_base_url.startswith(("http://", "https://")):
        raise RuntimeError("PUBLIC_BASE_URL must be an absolute URL")

