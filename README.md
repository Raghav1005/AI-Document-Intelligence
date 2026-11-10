# Local AI Document Intelligence & RAG Platform

A locally hosted document processing and retrieval-augmented chat platform. The application uses Next.js, FastAPI, Keycloak for OIDC identity, PostgreSQL and pgvector for persistence, and Ollama for local inference.

## Current status

The repository contains the infrastructure foundation, a protected Next.js workspace shell, Keycloak browser authentication, FastAPI JWT verification, and unit tests. Numeric OTP, application persistence, document processing, and chat remain planned feature work. The live Keycloak flow and Docker runtime still need end-to-end verification.

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

4. Open the workspace at [http://localhost:3000](http://localhost:3000), Keycloak at [http://localhost:8080](http://localhost:8080), Mailpit at [http://localhost:8025](http://localhost:8025), FastAPI at [http://localhost:8000](http://localhost:8000), and the Ollama local API at [http://localhost:11434](http://localhost:11434).

The app and vector databases do not publish host ports and share only the API data network with FastAPI and Ollama. The frontend shares the API proxy and identity-service networks, not the database network. Keycloak's database uses an isolated internal network; Keycloak and Mailpit share a separate SMTP network. Keycloak uses development configuration; do not expose this stack publicly.

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
| `backend` | FastAPI health/API process | `localhost:8000` |
| `frontend` | Next.js workspace UI and Keycloak public client | `localhost:3000` |

## Checks available at this stage

From the repository root, validate the Compose file with `docker compose --env-file .env.example config --quiet`. From `frontend/`, run `npm run typecheck`, `npm run lint`, and `npm run build`. From `backend/`, run `python -m pytest -p no:cacheprovider tests/`. Auth tests use a generated RSA key and do not contact a live Keycloak instance.

## Design notes

- The frontend uses the public Keycloak OIDC client with Authorization Code Flow and PKCE S256. Access/refresh tokens stay in memory and are not written to local or session storage.
- FastAPI validates JWT signature, issuer, expiration, and authorized client (`azp`) independently using Keycloak JWKS. An optional audience check is available when a Keycloak audience mapper is configured.
- Application and vector data are separate from Keycloak identity data.
- Local inference will not send documents or conversations to external AI APIs.
- Numeric email OTP may require a custom Keycloak extension; the default verification-link flow is not equivalent to a code-based OTP.
- Full architecture and known limitations are documented in `docs/ARCHITECTURE_DECISIONS.md` and `docs/LIMITATIONS_AND_TRADEOFFS.md`.

## Planned feature sequence

See the accepted architecture and feature order in `docs/ARCHITECTURE_DECISIONS.md`. Each logically complete feature should be developed on a focused branch and reviewed through a pull request targeting `develop`.
