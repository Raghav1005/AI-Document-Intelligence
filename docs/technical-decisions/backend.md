# Backend Framework Decision

**Status: Accepted for the API foundation.** The current implementation is a FastAPI process with liveness and basic readiness endpoints; auth, persistence, ingestion, and chat APIs are later feature work.

## Selected stack

Python 3.11+ and FastAPI expose asynchronous HTTP APIs with Pydantic request/response validation. SQLAlchemy will be used for relational access, with LangChain used only where it provides a concrete benefit. The current code is [backend/app/main.py](../../backend/app/main.py), dependencies are listed in [backend/requirements.txt](../../backend/requirements.txt), and [backend/Dockerfile](../../backend/Dockerfile) runs Uvicorn.

## Alternatives considered

### Flask

Flask is a small, mature WSGI framework with a large ecosystem and simple routing. Async support has improved, but FastAPI has native async route patterns and generates OpenAPI schemas directly from Pydantic types. Flask may be better for a small synchronous API or an existing Flask codebase.

### Django / Django REST Framework

Django includes ORM, migrations, admin, authentication, and a broad application structure. It is a strong choice when server-rendered web pages, admin workflows, or a large relational domain dominate. For this API, Keycloak owns identity, FastAPI provides lightweight async endpoints, and the application needs a focused ingestion/inference pipeline. Django would remain viable if the admin and relational domain expanded substantially.

### Node.js API frameworks

Node frameworks can share types with a TypeScript frontend and serve many concurrent I/O requests. Python has the stronger library ecosystem for document parsing, embeddings, and local model orchestration, avoiding a cross-language inference layer.

## Benefits

- Async request handling is suitable for streaming and I/O-bound work.
- Pydantic models validate input and produce API schemas.
- Python libraries support document extraction and local model runtimes.
- The framework remains small enough to keep service responsibilities visible.

## Costs and limits

- CPU-heavy parsing and embedding can block a process unless offloaded to a worker or thread/process pool.
- Async does not make CPU-bound work faster; it improves I/O concurrency.
- Dependency and type-checking discipline is needed as Python is dynamically typed.
- FastAPI does not supply authentication policy, migrations, or job queues automatically.

## Revisit when

Consider Django if built-in admin, ORM workflows, and integrated server features become central. Consider a Node API if language unification materially reduces complexity and Python inference can be cleanly isolated. Consider a dedicated task broker when processing volume or retry needs exceed a simple local worker queue.
