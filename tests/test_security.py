import time

from app.security import (
    hash_password,
    normalize_domain,
    normalize_phone,
    sign_request,
    verify_password,
    verify_request_signature,
)


def test_password_phone_domain_and_signature():
    password_hash = hash_password("A-secure-password-123")
    assert verify_password(password_hash, "A-secure-password-123")
    assert not verify_password(password_hash, "wrong-password")
    assert normalize_phone("+98 912 345 6789") == "9123456789"
    assert normalize_domain("https://Example.COM/") == "example.com"
    timestamp = str(int(time.time()))
    body = b'{"phone":"09123456789"}'
    signature = sign_request("secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", body)
    assert verify_request_signature(
        "secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", body, signature
    )
    assert not verify_request_signature(
        "secret", timestamp, "POST", "/abrehamrahi/v1/auth/sms/request", b"changed", signature
    )

