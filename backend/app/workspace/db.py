"""Database schema and connection for workspace records and pgvector chunks."""

import asyncio
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.workspace.settings import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


_schema_lock = asyncio.Lock()
_schema_ready = False


async def ensure_schema(engine: AsyncEngine | None = None) -> None:
    global _schema_ready
    if _schema_ready:
        return
    async with _schema_lock:
        if _schema_ready:
            return
        db = engine or get_engine()
        async with db.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS workspace_schema_migrations (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS workspace_conversations (
                    id UUID PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            await connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_workspace_conversations_owner_updated
                ON workspace_conversations (owner_id, updated_at DESC)
            """))
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS workspace_documents (
                    id UUID PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
                    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            await connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_workspace_documents_owner_created
                ON workspace_documents (owner_id, created_at DESC)
            """))
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS workspace_messages (
                    id UUID PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES workspace_conversations(id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    client_message_id TEXT,
                    reply_to UUID REFERENCES workspace_messages(id),
                    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('processing', 'completed', 'failed')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (owner_id, conversation_id, client_message_id)
                )
            """))
            await connection.execute(text("""
                ALTER TABLE workspace_messages ADD COLUMN IF NOT EXISTS
                    reply_to UUID REFERENCES workspace_messages(id)
            """))
            await connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_workspace_messages_conversation
                ON workspace_messages (owner_id, conversation_id, created_at)
            """))
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS workspace_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    document_id UUID NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER,
                    content TEXT NOT NULL,
                    embedding vector(768) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (document_id, chunk_index)
                )
            """))
            await connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_workspace_chunks_owner_document
                ON workspace_chunks (owner_id, document_id)
            """))
            await connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_workspace_chunks_embedding
                ON workspace_chunks USING hnsw (embedding vector_cosine_ops)
            """))
            await connection.execute(text("""
                INSERT INTO workspace_schema_migrations (migration_id)
                VALUES ('001_workspace_chat_documents_vectors')
                ON CONFLICT (migration_id) DO NOTHING
            """))
        _schema_ready = True
