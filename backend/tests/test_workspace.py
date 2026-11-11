"""Unit and Docker integration coverage for the local workspace pipeline."""

import asyncio
import io
import os
import time
from uuid import UUID, uuid4

import pymupdf as fitz
import pytest
from httpx import ASGITransport, AsyncClient
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.api.workspace import get_workspace_store
from app.auth.keycloak import get_email_verified_claims
from app.main import app
from sqlalchemy import text as sql_text
from app.workspace.db import ensure_schema, get_engine
from app.workspace.files import split_chunks, validate_content
from app.workspace.ollama import OllamaUnavailable


def text_docx(text: str) -> bytes:
    output = io.BytesIO()
    document = DocxDocument()
    document.add_paragraph(text)
    document.save(output)
    return output.getvalue()


def text_pdf(text: str) -> bytes:
    output = io.BytesIO()
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=16)
    output.write(document.tobytes())
    document.close()
    return output.getvalue()


def text_image(text: str, image_format: str) -> bytes:
    image = Image.new("RGB", (900, 190), "white")
    draw = ImageDraw.Draw(image)
    draw.text((25, 45), text, fill="black", font=ImageFont.load_default(size=48))
    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


@pytest.mark.parametrize(
    ("extension", "content", "expected"),
    [
        (".pdf", b"%PDF-1.7 sample", "application/pdf"),
        (".txt", "Hello, world".encode(), "text/plain"),
        (".png", text_image("TEST", "PNG"), "image/png"),
        (".jpg", text_image("TEST", "JPEG"), "image/jpeg"),
    ],
)
def test_actual_file_signatures_are_validated(extension: str, content: bytes, expected: str) -> None:
    assert validate_content(extension, content) == expected


def test_docx_validation_checks_package_structure() -> None:
    assert validate_content(
        ".docx", text_docx("A valid document"),
    ) == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_filename_path_components_are_removed() -> None:
    from app.workspace.files import safe_filename

    assert safe_filename("../../private/report.txt") == "report.txt"
    assert safe_filename("..\\private\\report.txt") == "report.txt"


def test_invalid_content_type_and_encoding_are_rejected() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as bad_pdf:
        validate_content(".pdf", b"This is not a PDF")
    assert bad_pdf.value.status_code == 415
    with pytest.raises(HTTPException) as bad_text:
        validate_content(".txt", b"\xff\xfe\x00")
    assert bad_text.value.status_code == 415


def test_chunks_preserve_content_with_bounded_overlap() -> None:
    text = ("The project code is violet 7314. " * 140).strip()
    chunks = split_chunks(text, chunk_size=240, overlap=32)
    assert len(chunks) > 5
    assert all(len(chunk) <= 240 for chunk in chunks)
    assert "violet 7314" in " ".join(chunks)


def test_chunks_remove_nul_bytes_from_extracted_docx_text() -> None:
    chunks = split_chunks("Experiment number\x0042 was performed.")
    assert len(chunks) == 1
    assert "\x00" not in chunks[0]
    assert "42" in chunks[0]


def test_workspace_endpoints_reject_unauthenticated_requests() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/conversations").status_code == 401
        assert client.get("/api/v1/documents").status_code == 401


@pytest.mark.skipif(
    not (os.getenv("TEST_WORKSPACE_DATABASE_URL") or os.getenv("WORKSPACE_DATABASE_URL")),
    reason="Set TEST_WORKSPACE_DATABASE_URL to run PostgreSQL/Ollama integration tests.",
)
def test_live_workspace_chat_upload_ocr_and_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv("TEST_WORKSPACE_DATABASE_URL") or os.environ["WORKSPACE_DATABASE_URL"]
    monkeypatch.setenv("WORKSPACE_DATABASE_URL", database_url)
    get_engine.cache_clear()
    get_workspace_store.cache_clear()

    owner_id = f"workspace-test-{uuid4()}"
    app.dependency_overrides[get_email_verified_claims] = lambda: {
        "sub": owner_id,
        "email_verified": True,
    }
    try:
        async def exercise() -> None:
            await ensure_schema()
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            created = await client.post("/api/v1/conversations", json={"title": "Integration test"})
            assert created.status_code == 201, created.text
            conversation_id = created.json()["id"]
            first_message_payload = {
                "message": "Reply briefly: what is 2 plus 2?",
                "client_message_id": f"msg_{uuid4().hex}",
                "document_ids": [],
            }
            first_message = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json=first_message_payload,
            )
            assert first_message.status_code == 200, first_message.text
            assert first_message.json()["role"] == "assistant"
            assert first_message.json()["content"]
            repeated = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages", json=first_message_payload
            )
            assert repeated.status_code == 200
            assert repeated.json()["id"] == first_message.json()["id"]

            text = (
                "Experiment number: 7314. This experiment evaluates supervised learning models "
                "on the CIFAR dataset. The document is for local retrieval testing."
            )
            uploads = [
                ("files", ("notes.txt", text.encode(), "text/plain")),
                ("files", ("notes.docx", text_docx(text), "application/octet-stream")),
                ("files", ("notes.pdf", text_pdf(text), "application/pdf")),
                ("files", ("scan.png", text_image("OCR SAMPLE 4281", "PNG"), "image/png")),
                ("files", ("scan.jpg", text_image("OCR SAMPLE 4281", "JPEG"), "image/jpeg")),
                ("files", ("broken.pdf", b"%PDF-1.7 broken sample", "application/pdf")),
            ]
            invalid_upload = await client.post(
                "/api/v1/documents/upload",
                files={"files": ("spoofed.pdf", b"not a pdf", "application/pdf")},
            )
            assert invalid_upload.status_code == 415
            uploaded = await client.post("/api/v1/documents/upload", files=uploads)
            assert uploaded.status_code == 202, uploaded.text
            documents = uploaded.json()["documents"]
            assert len(documents) == 6
            deadline = time.monotonic() + 180
            statuses: dict[str, dict] = {}
            while time.monotonic() < deadline:
                status_response = await client.get("/api/v1/documents")
                assert status_response.status_code == 200
                statuses = {document["id"]: document for document in status_response.json()}
                if all(statuses[item["id"]]["status"] in {"completed", "failed"} for item in documents):
                    break
                await asyncio.sleep(1)
            for item in documents:
                current = statuses[item["id"]]
                expected = "failed" if current["filename"] == "broken.pdf" else "completed"
                assert current["status"] == expected, (current["filename"], current["error_message"])
                assert "/data/documents" not in (current["error_message"] or "")

            scanned_image = next(item for item in documents if item["filename"] == "scan.png")
            async with get_engine().connect() as connection:
                ocr_chunks = (await connection.execute(sql_text("""
                    SELECT content FROM workspace_chunks WHERE document_id=:id AND owner_id=:owner_id
                """), {"id": UUID(scanned_image["id"]), "owner_id": owner_id})).scalars().all()
            assert any("OCR SAMPLE" in chunk.upper() for chunk in ocr_chunks)

            docx_doc = next(item for item in documents if item["filename"] == "notes.docx")
            async with get_engine().connect() as connection:
                indexed_chunks = (await connection.execute(sql_text("""
                    SELECT content, vector_dims(embedding) AS embedding_dimensions
                    FROM workspace_chunks WHERE document_id=:id AND owner_id=:owner_id
                """), {"id": UUID(docx_doc["id"]), "owner_id": owner_id})).mappings().all()
            assert indexed_chunks
            assert all(row["embedding_dimensions"] == 768 for row in indexed_chunks)
            assert "7314" in " ".join(row["content"] for row in indexed_chunks)

            from app.workspace import processing as processing_module

            original_generate = processing_module.generate
            captured_prompts: list[list[dict[str, str]]] = []

            async def capture_generate(messages: list[dict[str, str]]) -> str:
                captured_prompts.append(messages)
                return await original_generate(messages)

            monkeypatch.setattr(processing_module, "generate", capture_generate)
            rag_message = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "message": "What is the experiment number in the selected document?",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [docx_doc["id"]],
                },
            )
            assert rag_message.status_code == 200, rag_message.text
            assert "7314" in rag_message.json()["content"]
            assert rag_message.json()["sources"]
            assert rag_message.json()["sources"][0]["filename"] == "notes.docx"
            assert captured_prompts
            prompt_text = "\n".join(message["content"] for message in captured_prompts[-1])
            assert "Experiment number: 7314" in prompt_text
            assert "[Source 1: notes.docx" in prompt_text

            unrelated = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "message": "What is the patient's blood type?",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [docx_doc["id"]],
                },
            )
            assert unrelated.status_code == 200, unrelated.text
            assert unrelated.json()["sources"] == []
            assert "7314" not in unrelated.json()["content"]
            unrelated_prompt = "\n".join(message["content"] for message in captured_prompts[-1])
            assert "no relevant excerpts were found" in unrelated_prompt

            broken_doc = next(item for item in documents if item["filename"] == "broken.pdf")
            retry = await client.post(f"/api/v1/documents/{broken_doc['id']}/retry")
            assert retry.status_code == 202, retry.text
            assert retry.json()["status"] == "pending"
            retry_deadline = time.monotonic() + 60
            while time.monotonic() < retry_deadline:
                current = await client.get(f"/api/v1/documents/{broken_doc['id']}")
                assert current.status_code == 200
                if current.json()["status"] == "failed":
                    break
                await asyncio.sleep(1)
            assert current.json()["status"] == "failed"

            async def unavailable(_messages):
                raise OllamaUnavailable("test model unavailable")

            from app.workspace import processing as processing_module
            original_generate = processing_module.generate
            processing_module.generate = unavailable
            try:
                failed_chat = await client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    json={
                        "message": "This should fail safely.",
                        "client_message_id": f"msg_{uuid4().hex}",
                        "document_ids": [],
                    },
                )
            finally:
                processing_module.generate = original_generate
            assert failed_chat.status_code == 503

            loaded = await client.get(f"/api/v1/conversations/{conversation_id}")
            assert loaded.status_code == 200
            assert len(loaded.json()["messages"]) == 6
            other_owner = f"another-test-owner-{uuid4()}"
            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": other_owner,
                "email_verified": True,
            }
            assert (await client.get(f"/api/v1/conversations/{conversation_id}")).status_code == 404
            assert (await client.get(f"/api/v1/documents/{docx_doc['id']}")).status_code == 404

            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": owner_id,
                "email_verified": True,
            }
            for item in documents:
                assert (await client.delete(f"/api/v1/documents/{item['id']}" )).status_code == 204
            async with get_engine().begin() as connection:
                await connection.execute(sql_text(
                    "DELETE FROM workspace_conversations WHERE id=:id AND owner_id=:owner_id"
                ), {"id": UUID(conversation_id), "owner_id": owner_id})
            await client.aclose()
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.pop(get_email_verified_claims, None)
        get_engine.cache_clear()
