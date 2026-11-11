from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegistrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(validation_alias="APP_DATABASE_URL")
    key_dir: str = Field(
        default="/run/secrets/registration", validation_alias="REGISTRATION_KEY_DIR"
    )
    email_provider: str = Field(default="mailpit", validation_alias="EMAIL_PROVIDER")
    smtp_host: str = Field(default="mailpit", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=False, validation_alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, validation_alias="SMTP_USE_SSL")
    smtp_from_email: str = Field(
        default="no-reply@local-ai.local",
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "SMTP_FROM"),
    )
    smtp_from_name: str = Field(default="Local AI", validation_alias="SMTP_FROM_NAME")
    keycloak_internal_url: str = Field(
        default="http://keycloak:8080", validation_alias="KEYCLOAK_INTERNAL_URL"
    )
    keycloak_realm: str = Field(default="local-ai", validation_alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(
        default="local-ai-frontend", validation_alias="KEYCLOAK_CLIENT_ID"
    )
    registration_client_id: str = Field(
        default="local-ai-registration", validation_alias="KEYCLOAK_REGISTRATION_CLIENT_ID"
    )
    registration_client_secret_file: str = Field(
        default="/run/secrets/registration/keycloak-client-secret",
        validation_alias="KEYCLOAK_REGISTRATION_CLIENT_SECRET_FILE",
    )

    @model_validator(mode="after")
    def validate_email_settings(self) -> "RegistrationSettings":
        if self.email_provider not in {"mailpit", "smtp"}:
            raise ValueError("EMAIL_PROVIDER must be 'mailpit' or 'smtp'.")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("Provide both SMTP_USERNAME and SMTP_PASSWORD, or neither.")
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("Configure either SMTP STARTTLS or SSL, not both.")
        if not self.smtp_from_email.strip() or not self.smtp_from_name.strip():
            raise ValueError("Configure a sender email address and display name.")
        return self


@lru_cache(maxsize=1)
def get_registration_settings() -> RegistrationSettings:
    return RegistrationSettings()
