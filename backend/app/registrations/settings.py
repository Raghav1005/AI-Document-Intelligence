from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegistrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(validation_alias="APP_DATABASE_URL")
    key_dir: str = Field(
        default="/run/secrets/registration", validation_alias="REGISTRATION_KEY_DIR"
    )
    smtp_host: str = Field(default="mailpit", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=False, validation_alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, validation_alias="SMTP_USE_SSL")
    smtp_from: str = Field(default="no-reply@local-ai.local", validation_alias="SMTP_FROM")
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


@lru_cache(maxsize=1)
def get_registration_settings() -> RegistrationSettings:
    return RegistrationSettings()
