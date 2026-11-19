from __future__ import annotations

from typing import Any

import httpx


class UpstreamError(Exception):
    def __init__(self, status_code: int, message: str, detail: Any = None):
        self.status_code = status_code
        self.message = message
        self.detail = detail
        super().__init__(message)


class UpstreamClient:
    def __init__(self, origin: str, timeout: float):
        self.origin = origin.rstrip("/")
        self.timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Accept-Language": "fa",
            "User-Agent": "AbrehamrahiWebGateway/1.0",
            "user-device": "web",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.request(
                    method,
                    self.origin + path,
                    headers=headers,
                    json=json,
                    params=params,
                )
        except httpx.RequestError as exc:
            raise UpstreamError(502, "اتصال به ابرهمراهی برقرار نشد") from exc
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise UpstreamError(response.status_code, "ابرهمراهی درخواست را نپذیرفت", detail)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamError(502, "پاسخ ابرهمراهی JSON معتبر نبود") from exc

    async def login(self, phone: str, *, password: str | None = None, code: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"phone": phone, "prefix": "+98", "country": "IR"}
        if password is not None:
            payload["password"] = password
        if code is not None:
            payload["code"] = code
        result = await self.request("POST", "/api/v6/profile/auth/login/", json=payload)
        if not isinstance(result, dict) or not result.get("access"):
            raise UpstreamError(502, "توکن ورود در پاسخ ابرهمراهی موجود نیست")
        return result

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        result = await self.request(
            "POST", "/api/v2/profile/auth/token-refresh/", json={"refresh": refresh_token}
        )
        if not isinstance(result, dict) or not result.get("access"):
            raise UpstreamError(401, "نشست ابرهمراهی قابل تمدید نیست")
        return result

