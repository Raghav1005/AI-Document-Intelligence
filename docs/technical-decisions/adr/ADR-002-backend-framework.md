# ADR-002: Use FastAPI for the Python API

- **Status:** Accepted for the API foundation
- **Date:** 2026-11-10

## Context

The platform needs Python APIs for asynchronous document processing, retrieval, local model orchestration, and streaming. The initial implementation exposes process health only.

## Problem statement

Select a framework that supports async HTTP APIs, explicit validation, and the Python AI/document ecosystem without duplicating identity management.

## Decision

Use FastAPI, Pydantic, and Uvicorn. Use SQLAlchemy for relational persistence when database features are implemented. Use LangChain only when a specific feature justifies its abstractions.

## Alternatives considered

Flask, Django/DRF, and a TypeScript/Node API.

## Reasons for rejecting alternatives

Flask's async/API schema model is less direct for this project. Django/DRF carries useful integrated admin and ORM features, but the service is a focused API and Keycloak supplies identity. Node offers frontend type reuse but adds a Python boundary for document and model libraries.

## Advantages

Native async patterns, Pydantic validation, OpenAPI generation, and Python library compatibility.

## Disadvantages

Async does not accelerate CPU-bound work; worker isolation is needed. FastAPI does not include job scheduling, migrations, or application authorization by default.

## Risks and limitations

The health routes do not yet verify database, Keycloak, or Ollama dependencies. They are infrastructure scaffolding rather than a production readiness contract.

## Consequences

The API will remain responsible for JWT validation and user-level authorization even though Keycloak issues tokens. See [backend.md](../backend.md) and [backend/app/main.py](../../../backend/app/main.py).

## Conditions for revisiting

Revisit if integrated admin/domain workflows dominate, Python dependencies are no longer needed, or processing moves to separate services.
