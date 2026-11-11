"""Unit and Docker integration coverage for the local workspace pipeline."""

import asyncio
import io
import os
import re
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


def experiment_docx() -> bytes:
    output = io.BytesIO()
    document = DocxDocument()
    document.add_paragraph("The project code is violet 7314.")
    document.add_paragraph("EXPERIMENT 6: Evaluate the first model on CIFAR.")
    document.add_paragraph(
        "Unrelated notes describe data preparation, image normalization, training schedules, "
        "validation metrics, and routine laboratory procedures. " * 35
    )
    document.add_paragraph("EXPERIMENT 7: Compare the second model against the baseline.")
    document.add_paragraph("The appendix refers to EXPERIMENT 7 again.")
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
        assert client.delete(f"/api/v1/conversations/{uuid4()}").status_code == 401


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
                ("files", ("experiments.docx", experiment_docx(), "application/octet-stream")),
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
            assert len(documents) == 7
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
            experiment_document = next(item for item in documents if item["filename"] == "experiments.docx")
            async with get_engine().connect() as connection:
                indexed_chunks = (await connection.execute(sql_text("""
                    SELECT content, vector_dims(embedding) AS embedding_dimensions
                    FROM workspace_chunks WHERE document_id=:id AND owner_id=:owner_id
                """), {"id": UUID(docx_doc["id"]), "owner_id": owner_id})).mappings().all()
            assert indexed_chunks
            assert all(row["embedding_dimensions"] == 768 for row in indexed_chunks)
            assert "7314" in " ".join(row["content"] for row in indexed_chunks)

            async with get_engine().connect() as connection:
                experiment_chunks = (await connection.execute(sql_text("""
                    SELECT chunk_index, content FROM workspace_chunks
                    WHERE document_id=:id AND owner_id=:owner_id ORDER BY chunk_index
                """), {"id": UUID(experiment_document["id"]), "owner_id": owner_id})).mappings().all()
            six_indices = [row["chunk_index"] for row in experiment_chunks if "EXPERIMENT 6" in row["content"]]
            seven_indices = [row["chunk_index"] for row in experiment_chunks if "EXPERIMENT 7" in row["content"]]
            assert six_indices and seven_indices and min(six_indices) < min(seven_indices)
            assert any(
                six_indices[0] < row["chunk_index"] < seven_indices[0]
                and "EXPERIMENT" not in row["content"]
                for row in experiment_chunks
            )

            from app.workspace import processing as processing_module

            ollama_generate = processing_module.generate
            captured_prompts: list[list[dict[str, str]]] = []

            async def capture_generate(messages: list[dict[str, str]]) -> str:
                captured_prompts.append(messages)
                return await ollama_generate(messages)

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

            all_experiments = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "message": "List all experiment no.",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [experiment_document["id"]],
                },
            )
            assert all_experiments.status_code == 200, all_experiments.text
            answer = all_experiments.json()["content"]
            answer_numbers = re.findall(r"\bEXPERIMENT\s*[-:#]?\s*(\d+)\b", answer, re.IGNORECASE)
            assert set(answer_numbers) == {"6", "7"}
            assert answer_numbers.count("6") == 1
            assert answer_numbers.count("7") == 1
            all_sources = all_experiments.json()["sources"]
            cited_source_indices = {int(index) for index in re.findall(r"\[(\d+)\]", answer)}
            assert all(source["document_id"] == experiment_document["id"] for source in all_sources)
            assert all(source["filename"] == "experiments.docx" for source in all_sources)
            assert all(source["chunk_index"] is not None for source in all_sources)
            assert cited_source_indices
            assert cited_source_indices <= {source["index"] for source in all_sources}
            all_prompt = "\n".join(message["content"] for message in captured_prompts[-1])
            assert "EXPERIMENT 6" in all_prompt and "EXPERIMENT 7" in all_prompt
            assert "deduplicate repeated mentions" in all_prompt

            experiment_seven = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "message": "Tell me about EXPERIMENT 7.",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [experiment_document["id"]],
                },
            )
            assert experiment_seven.status_code == 200, experiment_seven.text
            assert "7" in experiment_seven.json()["content"]
            assert "6" not in experiment_seven.json()["content"]
            assert experiment_seven.json()["sources"]
            assert all(
                source["document_id"] == experiment_document["id"]
                for source in experiment_seven.json()["sources"]
            )
            specific_prompt = "\n".join(message["content"] for message in captured_prompts[-1])
            assert "EXPERIMENT 7" in specific_prompt
            assert "EXPERIMENT 6" not in specific_prompt

            normal_fact = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "message": "What is the project code?",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [experiment_document["id"]],
                },
            )
            assert normal_fact.status_code == 200, normal_fact.text
            assert "violet 7314" in normal_fact.json()["content"].lower()
            assert normal_fact.json()["sources"]

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
            assert len(loaded.json()["messages"]) == 12
            other_owner = f"another-test-owner-{uuid4()}"
            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": other_owner,
                "email_verified": True,
            }
            assert (await client.get(f"/api/v1/conversations/{conversation_id}")).status_code == 404
            assert (await client.get(f"/api/v1/documents/{docx_doc['id']}")).status_code == 404
            other_conversation = await client.post("/api/v1/conversations", json={"title": "Cross-user test"})
            assert other_conversation.status_code == 201
            cross_user_message = await client.post(
                f"/api/v1/conversations/{other_conversation.json()['id']}/messages",
                json={
                    "message": "Read the other user's document.",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [experiment_document["id"]],
                },
            )
            assert cross_user_message.status_code == 404
            assert (await client.delete(
                f"/api/v1/conversations/{other_conversation.json()['id']}"
            )).status_code == 204

            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": owner_id,
                "email_verified": True,
            }
            renamed = await client.patch(
                f"/api/v1/conversations/{conversation_id}", json={"title": "Renamed integration"}
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["title"] == "Renamed integration"
            assert (await client.patch(
                f"/api/v1/conversations/{conversation_id}", json={"title": "   "}
            )).status_code == 422

            delete_target = await client.post("/api/v1/conversations", json={"title": "Delete integration"})
            assert delete_target.status_code == 201
            delete_id = UUID(delete_target.json()["id"])
            delete_message = await client.post(
                f"/api/v1/conversations/{delete_id}/messages",
                json={
                    "message": "Reply briefly: what is 2 plus 2?",
                    "client_message_id": f"msg_{uuid4().hex}",
                    "document_ids": [],
                },
            )
            assert delete_message.status_code == 200
            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": other_owner,
                "email_verified": True,
            }
            assert (await client.delete(f"/api/v1/conversations/{delete_id}")).status_code == 404
            app.dependency_overrides[get_email_verified_claims] = lambda: {
                "sub": owner_id,
                "email_verified": True,
            }
            assert (await client.delete(f"/api/v1/conversations/{delete_id}")).status_code == 204
            assert (await client.get(f"/api/v1/conversations/{delete_id}")).status_code == 404
            async with get_engine().connect() as connection:
                remaining_messages = await connection.scalar(sql_text("""
                    SELECT COUNT(*) FROM workspace_messages WHERE conversation_id=:id
                """), {"id": delete_id})
            assert remaining_messages == 0
            assert (await client.get(f"/api/v1/documents/{experiment_document['id']}")).status_code == 200
            for item in documents:
                assert (await client.delete(f"/api/v1/documents/{item['id']}" )).status_code == 204
            assert (await client.delete(f"/api/v1/conversations/{conversation_id}")).status_code == 204
            assert (await client.delete(f"/api/v1/conversations/{conversation_id}")).status_code == 404
            await client.aclose()
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.pop(get_email_verified_claims, None)
        get_engine.cache_clear()
