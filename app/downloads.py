from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

from .db import Database
from .dependencies import upstream_request_for_user
from .security import Crypto
from .upstream import UpstreamClient, UpstreamError


def _download_url(value: Any) -> str | None:
    """Find a safe signed download URL in an Abrehamrahi response."""
    if isinstance(value, dict):
        direct = value.get("download_url")
        if isinstance(direct, str) and urlparse(direct).scheme == "https":
            return direct
        for key in ("object", "result", "data"):
            found = _download_url(value.get(key))
            if found:
                return found
    return None


async def resolve_download_url(
    user: dict[str, Any],
    object_id: str,
    db: Database,
    crypto: Crypto,
    upstream: UpstreamClient,
) -> str:
    """Resolve a fresh download URL using the same object endpoint as the app.

    Newer Abrehamrahi deployments expose ``download_url`` on the object detail
    response. The older dedicated endpoint is retained only as a fallback.
    """
    encoded_id = quote(object_id, safe="")
    first_error: UpstreamError | None = None
    try:
        result = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "GET",
            f"/api/v2/flat/get-object/{encoded_id}/",
        )
        found = _download_url(result)
        if found:
            return found
    except UpstreamError as exc:
        first_error = exc

    try:
        result = await upstream_request_for_user(
            user,
            db,
            crypto,
            upstream,
            "GET",
            f"/api/v1/flat/get-download-url/{encoded_id}/",
        )
        found = _download_url(result)
        if found:
            return found
    except UpstreamError:
        if first_error is not None:
            raise first_error
        raise

    if first_error is not None:
        raise first_error
    raise UpstreamError(
        502,
        "لینک دانلود از ابرهمراهی دریافت نشد",
        {"object_id": object_id},
    )
