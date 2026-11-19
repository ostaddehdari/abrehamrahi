from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


class Crypto:
    def __init__(self, key: str):
        self.fernet = Fernet(key.encode())

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Encrypted database value cannot be decrypted") from exc


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_random_token(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) > 10:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or not digits.startswith("9"):
        raise ValueError("شماره موبایل ایران معتبر نیست")
    return digits


def normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    if not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("دامنه معتبر نیست")
    return parsed.hostname.encode("idna").decode("ascii")


def origin_domain(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return normalize_domain(value)
    except ValueError:
        return None


def signing_message(timestamp: str, method: str, path: str, body: bytes) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()
    return signing_message_from_hash(timestamp, method, path, body_hash)


def signing_message_from_hash(timestamp: str, method: str, path: str, body_hash: str) -> bytes:
    return f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}".encode()


def sign_request(secret: str, timestamp: str, method: str, path: str, body: bytes) -> str:
    return hmac.new(secret.encode(), signing_message(timestamp, method, path, body), hashlib.sha256).hexdigest()


def verify_request_signature(secret: str, timestamp: str, method: str, path: str, body: bytes, signature: str) -> bool:
    try:
        if abs(int(time.time()) - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    expected = sign_request(secret, timestamp, method, path, body)
    return hmac.compare_digest(expected, signature)


def verify_prehashed_request_signature(
    secret: str,
    timestamp: str,
    method: str,
    path: str,
    body_hash: str,
    signature: str,
) -> bool:
    try:
        if abs(int(time.time()) - int(timestamp)) > 300:
            return False
        if len(body_hash) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in body_hash):
            return False
    except ValueError:
        return False
    expected = hmac.new(
        secret.encode(), signing_message_from_hash(timestamp, method, path, body_hash.lower()), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
