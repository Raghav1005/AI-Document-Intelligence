# Local AI Document Intelligence & RAG Platform

A locally hosted document processing and retrieval-augmented chat platform. The accepted architecture uses Next.js as a UI and backend-for-frontend, FastAPI for APIs and orchestration, Keycloak for OIDC identity, PostgreSQL and pgvector for persistence, and Ollama for local inference.

## Current status

The repository contains the infrastructure foundation, a Next.js workspace shell, FastAPI process-health routes, and health-route tests. Authentication, OTP, persistence, document processing, and chat are planned feature work and are not yet implemented.

## Prerequisites

- Docker Desktop with Docker Compose support
- Enough disk space for persistent databases and local model weights
- A machine with a local CPU; GPU support is optional and will be configured separately if available

The initial model settings are placeholders for later backend integration. Hardware performance has not yet been measured.

## Start the infrastructure

1. Copy `.env.example` to `.env` and replace the development passwords with unique values.
2. Start the services:

   ```powershell
   docker compose up -d
   ```

3. Check service status:

   ```powershell
   docker compose ps
   ```

4. Open the workspace at [http://localhost:3000](http://localhost:3000), Keycloak at [http://localhost:8080](http://localhost:8080), Mailpit at [http://localhost:8025](http://localhost:8025), and the Ollama local API at [http://localhost:11434](http://localhost:11434). The API listens on port 8000 inside the Compose network and is intentionally not published to the host.

The app and vector databases do not publish host ports and share only the API data network with FastAPI and Ollama. The frontend shares only the API proxy and identity-service networks, not the database network. Keycloak's database uses an isolated internal network; Keycloak and Mailpit share a separate SMTP network. Keycloak uses development configuration; do not expose this stack publicly.

After the Ollama service is available, model downloads are explicit:

```powershell
docker compose --env-file .env up -d ollama
docker compose --env-file .env exec ollama ollama pull qwen2.5:3b-instruct-q4_K_M
docker compose --env-file .env exec ollama ollama pull embeddinggemma:latest
docker compose --env-file .env exec ollama ollama list
```

The model weights are stored in the `ollama-data` volume. Downloads need network access and disk space; subsequent inference uses the local runtime. These candidate models have not been benchmarked on the target PC.

## Persistent data

Named volumes retain application database data, vector data, Keycloak data, and Ollama model files. `docker compose down` stops and removes containers but keeps these volumes. Removing volumes destroys local data and model downloads.

## Current services

| Service | Purpose | Host access |
|---|---|---|
| `app-db` | Application PostgreSQL | Internal network only |
| `vector-db` | PostgreSQL with pgvector extension | Internal network only |
| `keycloak-db` | Keycloak persistence | Internal network only |
| `keycloak` | OIDC identity service | `localhost:8080` |
| `mailpit` | Development SMTP capture and inbox | `localhost:1025`, `localhost:8025` |
| `ollama` | Local model runtime | `localhost:11434` |
| `backend` | FastAPI health/API process | Internal network only |
| `frontend` | Next.js workspace UI and planned BFF | `localhost:3000` |

## Checks available at this stage

From the repository root, validate the Compose file with `docker compose --env-file .env.example config --quiet`. Run the current backend health tests with `python -m pytest -p no:cacheprovider tests/` from `backend/`. These tests cover only process health routes; they do not verify database, Keycloak, Ollama, or end-to-end behavior.

## Design notes

- The browser will use a Next.js BFF with a secure HttpOnly session cookie. Access and refresh tokens remain server-side.
- FastAPI will validate JWT signature, issuer, audience, expiration, and roles independently using Keycloak JWKS.
- Application and vector data are separate from Keycloak identity data.
- Local inference will not send documents or conversations to external AI APIs.
- Numeric email OTP may require a custom Keycloak extension; the default verification-link flow is not equivalent to a code-based OTP.
- Full architecture and known limitations are documented in `docs/ARCHITECTURE_DECISIONS.md` and `docs/LIMITATIONS_AND_TRADEOFFS.md`.

## Planned feature sequence

See the accepted architecture and feature order in `docs/ARCHITECTURE_DECISIONS.md`. Each logically complete feature should be developed on a focused branch and reviewed through a pull request targeting `develop`.
