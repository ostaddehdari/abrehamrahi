from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .security import normalize_phone


class SmsRequest(BaseModel):
    phone: str
    captcha_id: str | None = None
    captcha_value: str | None = None
    captcha_provider: str | None = None
    request_type: int = 1

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class SmsVerify(BaseModel):
    challenge_id: str
    code: int = Field(ge=1000, le=99999999)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class PasswordSetup(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    verification_code: int | None = Field(default=None, ge=1000, le=99999999)


class PasswordLogin(BaseModel):
    phone: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent: str | None = None


class RegisterCdn(BaseModel):
    name: str = Field(min_length=1, max_length=1024)
    parent_id: str | None = None
    mime_type: str | None = None
    size: int | None = Field(default=None, ge=0)


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    domain: str = Field(min_length=3, max_length=253)

