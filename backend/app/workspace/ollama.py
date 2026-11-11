"""Ollama embedding and chat client."""

from typing import Any

import httpx

from app.workspace.settings import get_settings


class OllamaUnavailable(Exception):
    pass


async def embed(text_value: str) -> list[float]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.ollama_url.rstrip('/')}/api/embeddings",
                json={"model": settings.embedding_model, "prompt": text_value},
            )
            response.raise_for_status()
            vector = response.json().get("embedding")
            if not isinstance(vector, list) or len(vector) != settings.embedding_dimensions:
                raise OllamaUnavailable("The embedding model returned an unexpected vector size.")
            return [float(value) for value in vector]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise OllamaUnavailable("The local embedding model is unavailable.") from error


async def generate(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.ollama_url.rstrip('/')}/api/chat",
                json={"model": settings.chat_model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            content: Any = response.json().get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise OllamaUnavailable("The local chat model returned an empty response.")
            return content.strip()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise OllamaUnavailable("The local chat model is unavailable.") from error
