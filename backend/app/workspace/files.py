"""Secure upload validation, storage, extraction, OCR, and text chunking."""

import asyncio
import hashlib
import io
import re
import zipfile
from pathlib import Path
from uuid import UUID

import pymupdf as fitz
import pytesseract
from docx import Document as DocxDocument
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.workspace.settings import get_settings

Image.MAX_IMAGE_PIXELS = 30_000_000

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


def safe_filename(value: str | None) -> str:
    filename = Path((value or "").replace("\\", "/")).name
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename).strip(" .")
    if not filename or len(filename) > 180:
        raise HTTPException(status_code=422, detail="The file name is invalid.")
    return filename


async def read_upload(upload: UploadFile) -> tuple[str, bytes, str]:
    filename = safe_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {extension or 'unknown'}.")
    content = await upload.read(get_settings().max_file_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(content) > get_settings().max_file_bytes:
        raise HTTPException(status_code=413, detail="Files must be 25 MB or smaller.")
    content_type = validate_content(extension, content)
    return filename, content, content_type


def validate_content(extension: str, content: bytes) -> str:
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="The file contents are not a valid PDF.")
        return "application/pdf"
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ValueError("Not a DOCX document")
                if sum(item.file_size for item in archive.infolist()) > 100_000_000:
                    raise ValueError("DOCX expands past the safe processing limit")
        except (zipfile.BadZipFile, ValueError) as error:
            raise HTTPException(status_code=415, detail="The file contents are not a valid DOCX document.") from error
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if extension == ".txt":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=415, detail="Text files must use UTF-8 encoding.") from error
        return "text/plain"
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            if extension == ".png" and image.format != "PNG":
                raise ValueError("extension/content mismatch")
            if extension in {".jpg", ".jpeg"} and image.format != "JPEG":
                raise ValueError("extension/content mismatch")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=415, detail="The image file is invalid or does not match its extension.") from error
    return "image/png" if extension == ".png" else "image/jpeg"


def storage_file(owner_id: str, document_id: UUID) -> Path:
    # Both path components are server-generated/verified, never the upload name.
    owner_key = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
    return Path(get_settings().storage_path) / owner_key / str(document_id)


def save_file(owner_id: str, document_id: UUID, content: bytes) -> Path:
    path = storage_file(owner_id, document_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(content)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


async def extract_text(path: Path, content_type: str) -> list[tuple[int | None, str]]:
    return await asyncio.to_thread(_extract_text_sync, path, content_type)


def _extract_text_sync(path: Path, content_type: str) -> list[tuple[int | None, str]]:
    if content_type == "text/plain":
        text = path.read_text(encoding="utf-8-sig")
        return [(None, text)]
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = DocxDocument(path)
        parts = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return [(None, "\n".join(parts))]
    try:
        if content_type == "application/pdf":
            results: list[tuple[int | None, str]] = []
            with fitz.open(path) as pdf:
                if len(pdf) > 500:
                    raise ValueError("PDF exceeds the 500-page processing limit.")
                for index, page in enumerate(pdf):
                    text = page.get_text("text").strip()
                    if len(text) < 40:
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                        text = pytesseract.image_to_string(image, lang="eng+hin").strip()
                    if text:
                        results.append((index + 1, text))
            return results
        with Image.open(path) as image:
            image.load()
            text = pytesseract.image_to_string(image, lang="eng+hin").strip()
        return [(None, text)]
    except pytesseract.TesseractNotFoundError as error:
        raise ValueError("The local OCR engine is unavailable.") from error


def split_chunks(text: str, *, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
    # PostgreSQL text columns reject NUL bytes. They can occur in otherwise
    # readable DOCX extraction output and previously caused the whole document
    # indexing transaction to fail.
    text = text.replace("\x00", " ")
    cleaned = re.sub(r"[\t\r ]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        if end < len(cleaned):
            boundary = max(cleaned.rfind("\n", start, end), cleaned.rfind(". ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks
