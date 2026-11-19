from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.security import hash_secret


class FakeUpstream:
    async def request(self, method, path, **kwargs):
        if path.endswith("generate-code/"):
            return {"status": "sent"}
        if path.endswith("change-password/"):
            return None
        if path.endswith("start-upload/"):
            return {
                "upload_id": "upload-1",
                "key": "object-key",
                "signed_urls": ["https://storage.invalid/1", "https://storage.invalid/2"],
                "chunk_size": 3,
            }
        if path.endswith("complete-upload/"):
            return {"id": "object-42", "name": "demo.txt"}
        if "get-download-url" in path:
            return {"download_url": "https://storage.invalid/download"}
        if path.endswith("list-objects/"):
            return {"count": 1, "results": [{"id": "object-42", "name": "demo.txt"}]}
        if path.endswith("get-quota/"):
            return {"total_space": 1000, "used_space": 250}
        if path.endswith("trash-objects/"):
            return {"status": "trashed"}
        if "delete-object" in path and method == "DELETE":
            return None
        raise AssertionError(f"unexpected upstream call: {method} {path}")

    async def login(self, phone, *, password=None, code=None):
        return {"access": "access-token", "refresh": "refresh-token", "is_registered": True}

    async def refresh(self, refresh_token):
        return {"access": "access-token-2", "refresh": "refresh-token-2"}


class FakeSignedStorage:
    counter = 0

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def put(self, url, content, headers):
        self.counter += 1
        return httpx.Response(200, headers={"ETag": f'"etag-{self.counter}"'})


def test_sms_password_list_and_upload(monkeypatch):
    with TestClient(app) as client:
        app.state.upstream = FakeUpstream()
        client_token = "abrc_test-token"
        secret = app.state.crypto.encrypt("abrsig_test-secret")
        import asyncio

        asyncio.run(
            app.state.db.execute(
                "INSERT INTO api_clients(name,domain,token_hash,encrypted_signing_secret,active,created_at) VALUES(?,?,?,?,1,1)",
                ("test", "example.com", hash_secret(client_token), secret),
            )
        )
        base_headers = {"Origin": "https://example.com", "X-ABR-Client-Token": client_token}
        sent = client.post("/v1/auth/sms/request", json={"phone": "09123456789"}, headers=base_headers)
        assert sent.status_code == 200, sent.text
        challenge = sent.json()["challenge_id"]

        verified = client.post(
            "/v1/auth/sms/verify",
            json={"challenge_id": challenge, "code": 12345, "new_password": "secure-password-123"},
            headers=base_headers,
        )
        assert verified.status_code == 200, verified.text
        session = verified.json()["session_token"]
        auth_headers = {**base_headers, "Authorization": f"Bearer {session}"}

        listed = client.get("/v1/files", headers=auth_headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["results"][0]["name"] == "demo.txt"
        assert listed.json()["results"][0]["cdn_url"].startswith(
            "https://srun.ir/abrehamrahi/cdn/"
        )

        quota = client.get("/v1/quota", headers=auth_headers)
        assert quota.status_code == 200, quota.text
        assert quota.json()["total"] == 1000
        assert quota.json()["used"] == 250
        assert quota.json()["remaining"] == 750

        admin_page = client.get("/testpage", auth=("admin", "test-admin-password"))
        assert admin_page.status_code == 200
        same_origin_headers = {
            "X-ABR-Client-Token": client_token,
            "Authorization": f"Bearer {session}",
        }
        quota_without_origin = client.get("/v1/quota", headers=same_origin_headers)
        assert quota_without_origin.status_code == 200, quota_without_origin.text

        monkeypatch.setattr("app.routers.files.httpx.AsyncClient", FakeSignedStorage)
        uploaded = client.post(
            "/v1/files/upload",
            files={"file": ("demo.txt", b"abcde", "text/plain")},
            data={"parent": "root"},
            headers=auth_headers,
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["object_id"] == "object-42"
        assert uploaded.json()["cdn_url"].startswith("https://srun.ir/abrehamrahi/cdn/")

        deleted = client.delete("/v1/files/object-42", headers=auth_headers)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["permanent"] is False


def test_testpage_is_admin_protected():
    with TestClient(app) as client:
        denied = client.get("/testpage")
        assert denied.status_code == 401
        page = client.get("/testpage", auth=("admin", "test-admin-password"))
        assert page.status_code == 200
        assert "آزمایشگاه API ابرهمراهی" in page.text
        assert "abr_testpage_admin=" in page.headers["set-cookie"]
        assert "HttpOnly" in page.headers["set-cookie"]

