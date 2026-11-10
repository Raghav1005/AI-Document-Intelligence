from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr = Field(max_length=254)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128, repr=False)
    confirm_password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("username", "email", "first_name", "last_name", mode="before")
    @classmethod
    def trim_profile_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def passwords_match(self) -> Self:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class VerifyOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_id: UUID
    otp: str = Field(pattern=r"^\d{4}$")


class ResendOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_id: UUID


class RegistrationPendingResponse(BaseModel):
    registration_id: UUID
    email: EmailStr
    expires_in_seconds: int
    resend_in_seconds: int


class RegistrationVerifiedResponse(BaseModel):
    status: str = "verified"
    detail: str = "Your email is verified. You can now sign in."
    email: EmailStr


class ResendOtpResponse(BaseModel):
    resend_in_seconds: int
    expires_in_seconds: int
