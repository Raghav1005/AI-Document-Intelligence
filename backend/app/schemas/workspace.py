from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    client_message_id: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    document_ids: list[UUID] = Field(default_factory=list, max_length=50)


class SourceReference(BaseModel):
    index: int
    document_id: UUID
    filename: str
    page: int | None = None


class MessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceReference] = Field(default_factory=list)
    status: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationListItem(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    status: Literal["pending", "processing", "completed", "failed"]
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    documents: list[DocumentResponse]
