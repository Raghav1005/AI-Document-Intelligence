from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkspaceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(validation_alias="WORKSPACE_DATABASE_URL")
    storage_path: str = Field(default="/data/documents", validation_alias="DOCUMENT_STORAGE_PATH")
    ollama_url: str = Field(default="http://ollama:11434", validation_alias="OLLAMA_BASE_URL")
    chat_model: str = Field(default="qwen2.5:3b-instruct-q4_K_M", validation_alias="OLLAMA_CHAT_MODEL")
    embedding_model: str = Field(default="embeddinggemma:latest", validation_alias="OLLAMA_EMBEDDING_MODEL")
    max_file_bytes: int = 25 * 1024 * 1024
    embedding_dimensions: int = 768


def get_settings() -> WorkspaceSettings:
    return WorkspaceSettings()
