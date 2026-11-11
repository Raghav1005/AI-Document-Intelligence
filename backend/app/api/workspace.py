"""Authenticated owner-scoped chat and document endpoints."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.auth.keycloak import get_email_verified_claims
from app.schemas.workspace import (
    ConversationCreate,
    ConversationListItem,
    ConversationRename,
    ConversationResponse,
    DocumentResponse,
    MessageCreate,
    MessageResponse,
    UploadResponse,
)
from app.workspace.files import read_upload, save_file, storage_file
from app.workspace.ollama import OllamaUnavailable
from app.workspace.processing import DocumentRetrievalUnavailable, answer_message
from app.workspace.store import WorkspaceStore

router = APIRouter(prefix="/api/v1", tags=["workspace"])
Claims = Annotated[dict[str, Any], Depends(get_email_verified_claims)]


@lru_cache(maxsize=1)
def get_workspace_store() -> WorkspaceStore:
    return WorkspaceStore()


Store = Annotated[WorkspaceStore, Depends(get_workspace_store)]


def owner(claims: dict[str, Any]) -> str:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 200:
        raise HTTPException(status_code=401, detail="The access token has no valid user identity.")
    return subject


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, claims: Claims, store: Store) -> dict:
    try:
        conversation = await store.create_conversation(owner(claims), payload.title.strip())
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Conversation storage is temporarily unavailable.") from error
    return {**conversation, "messages": []}


@router.get("/conversations", response_model=list[ConversationListItem])
async def list_conversations(claims: Claims, store: Store) -> list[dict]:
    try:
        return await store.list_conversations(owner(claims))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Conversation storage is temporarily unavailable.") from error


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: UUID, claims: Claims, store: Store) -> dict:
    try:
        conversation = await store.get_conversation(owner(claims), conversation_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Conversation storage is temporarily unavailable.") from error
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationListItem)
async def rename_conversation(
    conversation_id: UUID, payload: ConversationRename, claims: Claims, store: Store
) -> dict:
    try:
        conversation = await store.rename_conversation(
            owner(claims), conversation_id, payload.title,
        )
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Conversation storage is temporarily unavailable.") from error
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: UUID, claims: Claims, store: Store) -> None:
    try:
        deleted = await store.delete_conversation(owner(claims), conversation_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Conversation storage is temporarily unavailable.") from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(
    conversation_id: UUID, payload: MessageCreate, claims: Claims, store: Store
) -> dict:
    try:
        result = await answer_message(
            store=store,
            owner_id=owner(claims),
            conversation_id=conversation_id,
            client_message_id=payload.client_message_id,
            question=payload.message.strip(),
            document_ids=payload.document_ids,
        )
    except OllamaUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except DocumentRetrievalUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Chat storage is temporarily unavailable.") from error
    if result.get("error") == "conversation_not_found":
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if result.get("error") == "message_in_progress":
        raise HTTPException(status_code=409, detail="This message is already being processed.")
    return result["message"]


@router.post("/documents/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    claims: Claims, store: Store, files: Annotated[list[UploadFile], File(...) ]
) -> dict:
    if not files:
        raise HTTPException(status_code=422, detail="Choose at least one file to upload.")
    if len(files) > 10:
        raise HTTPException(status_code=413, detail="Upload at most ten files at a time.")
    parsed: list[tuple[str, bytes, str]] = []
    try:
        for upload in files:
            parsed.append(await read_upload(upload))
    finally:
        await asyncio.gather(*(upload.close() for upload in files))

    owner_id = owner(claims)
    stored: list[dict] = []
    paths: list[Path] = []
    document_ids: list[UUID] = []
    try:
        for filename, content, content_type in parsed:
            document = await store.insert_document(owner_id, filename, content_type, len(content))
            document_id = document["id"]
            document_ids.append(document_id)
            file_path = storage_file(owner_id, document_id)
            paths.append(file_path)
            save_file(owner_id, document_id, content)
            stored.append(document)
    except (OSError, SQLAlchemyError) as error:
        for path in paths:
            path.unlink(missing_ok=True)
        for document_id in document_ids:
            try:
                await store.delete_document(owner_id, document_id)
            except SQLAlchemyError:
                pass
        raise HTTPException(status_code=503, detail="The files could not be stored. Please try again.") from error
    return {"documents": stored}


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(claims: Claims, store: Store) -> list[dict]:
    try:
        return await store.list_documents(owner(claims))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.") from error


@router.post("/documents/{document_id}/retry", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_document(document_id: UUID, claims: Claims, store: Store) -> dict:
    try:
        document = await store.retry_failed_document(owner(claims), document_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.") from error
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document["status"] != "pending":
        raise HTTPException(status_code=409, detail="Only failed documents can be retried.")
    return document


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, claims: Claims, store: Store) -> dict:
    try:
        document = await store.get_document(owner(claims), document_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.") from error
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.get("/documents/{document_id}/status", response_model=DocumentResponse)
async def get_document_status(document_id: UUID, claims: Claims, store: Store) -> dict:
    return await get_document(document_id, claims, store)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, claims: Claims, store: Store) -> None:
    owner_id = owner(claims)
    try:
        deleted = await store.delete_document(owner_id, document_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.") from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    storage_file(owner_id, document_id).unlink(missing_ok=True)
