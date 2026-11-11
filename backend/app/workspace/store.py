"""Owner-scoped PostgreSQL operations for conversations, messages, and files."""

import json
from uuid import UUID, uuid4

from sqlalchemy import text

from app.workspace.db import ensure_schema, get_engine


class WorkspaceStore:
    async def create_conversation(self, owner_id: str, title: str = "New conversation") -> dict:
        await ensure_schema()
        conversation_id = uuid4()
        async with get_engine().begin() as connection:
            row = (await connection.execute(text("""
                INSERT INTO workspace_conversations (id, owner_id, title)
                VALUES (:id, :owner_id, :title)
                RETURNING id, owner_id, title, created_at, updated_at
            """), {"id": conversation_id, "owner_id": owner_id, "title": title})).mappings().one()
        return dict(row)

    async def list_conversations(self, owner_id: str) -> list[dict]:
        await ensure_schema()
        async with get_engine().connect() as connection:
            rows = (await connection.execute(text("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT content FROM workspace_messages m
                        WHERE m.conversation_id=c.id AND m.owner_id=c.owner_id
                        ORDER BY m.created_at DESC LIMIT 1) AS last_message
                FROM workspace_conversations c
                WHERE c.owner_id=:owner_id
                ORDER BY c.updated_at DESC LIMIT 100
            """), {"owner_id": owner_id})).mappings().all()
        return [dict(row) for row in rows]

    async def get_conversation(self, owner_id: str, conversation_id: UUID) -> dict | None:
        await ensure_schema()
        async with get_engine().connect() as connection:
            row = (await connection.execute(text("""
                SELECT id, title, created_at, updated_at FROM workspace_conversations
                WHERE id=:id AND owner_id=:owner_id
            """), {"id": conversation_id, "owner_id": owner_id})).mappings().first()
            if row is None:
                return None
            messages = (await connection.execute(text("""
                SELECT id, role, content, sources, status, created_at
                FROM workspace_messages
                WHERE conversation_id=:id AND owner_id=:owner_id AND status='completed'
                ORDER BY created_at ASC
            """), {"id": conversation_id, "owner_id": owner_id})).mappings().all()
        result = dict(row)
        result["messages"] = [dict(message) for message in messages]
        return result

    async def begin_message(
        self, *, owner_id: str, conversation_id: UUID, client_message_id: str, content: str
    ) -> tuple[str, dict | None]:
        """Return (new|retry|cached|busy, cached answer) under an idempotency lock."""
        await ensure_schema()
        message_id = uuid4()
        async with get_engine().begin() as connection:
            exists = (await connection.execute(text("""
                SELECT id FROM workspace_conversations WHERE id=:id AND owner_id=:owner_id FOR UPDATE
            """), {"id": conversation_id, "owner_id": owner_id})).first()
            if exists is None:
                return "missing", None
            inserted = (await connection.execute(text("""
                INSERT INTO workspace_messages
                    (id, conversation_id, owner_id, role, content, client_message_id, status)
                VALUES (:id, :conversation_id, :owner_id, 'user', :content, :client_message_id, 'processing')
                ON CONFLICT (owner_id, conversation_id, client_message_id) DO NOTHING
                RETURNING id
            """), {
                "id": message_id, "conversation_id": conversation_id, "owner_id": owner_id,
                "content": content, "client_message_id": client_message_id,
            })).first()
            if inserted is not None:
                await connection.execute(text("""
                    UPDATE workspace_conversations SET updated_at=NOW(),
                    title=CASE WHEN title='New conversation' THEN LEFT(:content, 72) ELSE title END
                    WHERE id=:id AND owner_id=:owner_id
                """), {"id": conversation_id, "owner_id": owner_id, "content": content})
                return "new", None

            prior = (await connection.execute(text("""
                SELECT id, content, status FROM workspace_messages
                WHERE owner_id=:owner_id AND conversation_id=:conversation_id
                  AND client_message_id=:client_message_id FOR UPDATE
            """), {
                "owner_id": owner_id, "conversation_id": conversation_id,
                "client_message_id": client_message_id,
            })).mappings().one()
            answer = (await connection.execute(text("""
                SELECT id, role, content, sources, status, created_at FROM workspace_messages
                WHERE owner_id=:owner_id AND conversation_id=:conversation_id AND reply_to=:user_id
                LIMIT 1
            """), {
                "owner_id": owner_id, "conversation_id": conversation_id,
                "user_id": prior["id"],
            })).mappings().first()
            if answer:
                return "cached", dict(answer)
            if prior["status"] == "processing":
                return "busy", None
            await connection.execute(text("""
                UPDATE workspace_messages SET status='processing' WHERE id=:id
            """), {"id": prior["id"]})
            return "retry", None

    async def complete_message(
        self, *, owner_id: str, conversation_id: UUID, client_message_id: str,
        answer: str, sources: list[dict],
    ) -> dict:
        await ensure_schema()
        message_id = uuid4()
        async with get_engine().begin() as connection:
            user = (await connection.execute(text("""
                SELECT id FROM workspace_messages WHERE owner_id=:owner_id AND conversation_id=:conversation_id
                  AND role='user' AND client_message_id=:client_message_id
            """), {
                "owner_id": owner_id, "conversation_id": conversation_id,
                "client_message_id": client_message_id,
            })).mappings().one()
            await connection.execute(text("""
                UPDATE workspace_messages SET status='completed' WHERE id=:id
            """), {"id": user["id"]})
            row = (await connection.execute(text("""
                INSERT INTO workspace_messages (id, conversation_id, owner_id, role, content, sources, reply_to)
                VALUES (:id, :conversation_id, :owner_id, 'assistant', :answer, CAST(:sources AS JSONB), :reply_to)
                RETURNING id, role, content, sources, status, created_at
            """), {
                "id": message_id, "conversation_id": conversation_id, "owner_id": owner_id,
                "answer": answer, "sources": json.dumps(sources), "reply_to": user["id"],
            })).mappings().one()
            await connection.execute(text("""
                UPDATE workspace_conversations SET updated_at=NOW()
                WHERE id=:id AND owner_id=:owner_id
            """), {"id": conversation_id, "owner_id": owner_id})
        return dict(row)

    async def fail_message(self, owner_id: str, conversation_id: UUID, client_message_id: str) -> None:
        await ensure_schema()
        async with get_engine().begin() as connection:
            await connection.execute(text("""
                UPDATE workspace_messages SET status='failed'
                WHERE owner_id=:owner_id AND conversation_id=:conversation_id
                  AND role='user' AND client_message_id=:client_message_id
            """), {
                "owner_id": owner_id, "conversation_id": conversation_id,
                "client_message_id": client_message_id,
            })

    async def list_documents(self, owner_id: str) -> list[dict]:
        await ensure_schema()
        async with get_engine().connect() as connection:
            rows = (await connection.execute(text("""
                SELECT id, filename, content_type, size_bytes, status, error_message, created_at, updated_at
                FROM workspace_documents WHERE owner_id=:owner_id ORDER BY created_at DESC LIMIT 500
            """), {"owner_id": owner_id})).mappings().all()
        return [dict(row) for row in rows]

    async def get_document(self, owner_id: str, document_id: UUID) -> dict | None:
        await ensure_schema()
        async with get_engine().connect() as connection:
            row = (await connection.execute(text("""
                SELECT id, owner_id, filename, content_type, size_bytes, status, error_message, created_at, updated_at
                FROM workspace_documents WHERE id=:id AND owner_id=:owner_id
            """), {"id": document_id, "owner_id": owner_id})).mappings().first()
        return dict(row) if row else None

    async def insert_document(self, owner_id: str, filename: str, content_type: str, size_bytes: int) -> dict:
        await ensure_schema()
        document_id = uuid4()
        async with get_engine().begin() as connection:
            row = (await connection.execute(text("""
                INSERT INTO workspace_documents (id, owner_id, filename, content_type, size_bytes, status)
                VALUES (:id, :owner_id, :filename, :content_type, :size_bytes, 'pending')
                RETURNING id, filename, content_type, size_bytes, status, error_message, created_at, updated_at
            """), {
                "id": document_id, "owner_id": owner_id, "filename": filename,
                "content_type": content_type, "size_bytes": size_bytes,
            })).mappings().one()
        return dict(row)

    async def delete_document(self, owner_id: str, document_id: UUID) -> bool:
        await ensure_schema()
        async with get_engine().begin() as connection:
            result = await connection.execute(text("""
                DELETE FROM workspace_documents WHERE id=:id AND owner_id=:owner_id
            """), {"id": document_id, "owner_id": owner_id})
        return result.rowcount > 0

    async def claim_document(self) -> dict | None:
        await ensure_schema()
        async with get_engine().begin() as connection:
            row = (await connection.execute(text("""
                WITH next_job AS (
                    SELECT id FROM workspace_documents WHERE status='pending'
                    ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE workspace_documents d SET status='processing', error_message=NULL, updated_at=NOW()
                FROM next_job WHERE d.id=next_job.id
                RETURNING d.id, d.owner_id, d.filename, d.content_type, d.size_bytes
            """))).mappings().first()
        return dict(row) if row else None

    async def store_chunks(self, document: dict, chunks: list[dict]) -> None:
        await ensure_schema()
        async with get_engine().begin() as connection:
            await connection.execute(text("DELETE FROM workspace_chunks WHERE document_id=:id"), {"id": document["id"]})
            for chunk in chunks:
                vector = "[" + ",".join(f"{value:.9g}" for value in chunk["embedding"]) + "]"
                await connection.execute(text("""
                    INSERT INTO workspace_chunks
                        (document_id, owner_id, chunk_index, page_number, content, embedding)
                    VALUES (:document_id, :owner_id, :chunk_index, :page_number, :content, CAST(:embedding AS vector))
                """), {
                    "document_id": document["id"], "owner_id": document["owner_id"],
                    "chunk_index": chunk["index"], "page_number": chunk["page"],
                    "content": chunk["content"], "embedding": vector,
                })
            await connection.execute(text("""
                UPDATE workspace_documents SET status='completed', error_message=NULL, updated_at=NOW()
                WHERE id=:id AND status='processing'
            """), {"id": document["id"]})

    async def fail_document(self, document_id: UUID, message: str) -> None:
        await ensure_schema()
        async with get_engine().begin() as connection:
            await connection.execute(text("""
                UPDATE workspace_documents SET status='failed', error_message=:message, updated_at=NOW()
                WHERE id=:id AND status='processing'
            """), {"id": document_id, "message": message[:500]})

    async def retry_failed_document(self, owner_id: str, document_id: UUID) -> dict | None:
        """Queue only an owned document that is currently failed for reprocessing."""
        await ensure_schema()
        async with get_engine().begin() as connection:
            row = (await connection.execute(text("""
                UPDATE workspace_documents
                SET status='pending', error_message=NULL, updated_at=NOW()
                WHERE id=:id AND owner_id=:owner_id AND status='failed'
                RETURNING id, filename, content_type, size_bytes, status, error_message, created_at, updated_at
            """), {"id": document_id, "owner_id": owner_id})).mappings().first()
        if row is not None:
            return dict(row)
        return await self.get_document(owner_id, document_id)

    async def retrieve_chunks(
        self, *, owner_id: str, document_ids: list[UUID], embedding: list[float],
        limit: int = 8, max_distance: float = 0.72,
    ) -> list[dict]:
        await ensure_schema()
        vector = "[" + ",".join(f"{value:.9g}" for value in embedding) + "]"
        async with get_engine().connect() as connection:
            rows = (await connection.execute(text("""
                SELECT c.document_id, d.filename, c.page_number, c.chunk_index, c.content,
                       c.embedding <=> CAST(:embedding AS vector) AS distance
                FROM workspace_chunks c
                JOIN workspace_documents d ON d.id=c.document_id AND d.owner_id=c.owner_id
                WHERE c.owner_id=:owner_id AND d.status='completed' AND c.document_id=ANY(:document_ids)
                  AND c.embedding <=> CAST(:embedding AS vector) <= :max_distance
                ORDER BY c.embedding <=> CAST(:embedding AS vector) LIMIT :limit
            """), {
                "owner_id": owner_id, "document_ids": document_ids,
                "embedding": vector, "limit": limit, "max_distance": max_distance,
            })).mappings().all()
        return [dict(row) for row in rows]

    async def validate_selected_documents(self, *, owner_id: str, document_ids: list[UUID]) -> list[str]:
        """Verify every requested document belongs to the caller and is indexed."""
        await ensure_schema()
        async with get_engine().connect() as connection:
            rows = (await connection.execute(text("""
                SELECT id, status FROM workspace_documents
                WHERE owner_id=:owner_id AND id=ANY(:document_ids)
            """), {"owner_id": owner_id, "document_ids": document_ids})).all()
        statuses = {row.id: row.status for row in rows}
        if len(statuses) != len(set(document_ids)):
            raise PermissionError("One or more selected documents are unavailable.")
        unavailable = [status for status in statuses.values() if status != "completed"]
        return unavailable
