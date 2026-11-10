# Docker and Deployment Decision

**Status: Accepted for the local development MVP.** This note reflects the current Compose foundation; it does not claim the complete application is deployed.

## Decision

Use Docker Compose to run independent containers on one local PC. The current stack defines PostgreSQL for app data, PostgreSQL with pgvector for vector data, PostgreSQL for Keycloak, Keycloak, Mailpit, and Ollama. Database/model storage uses named volumes. Host ports bind to `127.0.0.1` by default. The implementation is in [docker-compose.yml](../../docker-compose.yml).

## Why Compose

Compose provides repeatable service startup, private container networking, health dependencies, and persistent volumes without requiring a cluster. It is a good fit for a single-user local installation and lowers the operational cost of the MVP.

## Alternatives and trade-offs

- **Kubernetes:** better for multi-host scheduling, service scaling, and deployment policy; materially more operational complexity and resource use for one PC.
- **Direct host installation:** can reduce container overhead but makes dependency versions, ports, and startup order harder to reproduce.
- **One PostgreSQL instance with multiple databases:** reduces container memory and administration overhead. The current design instead separates application, vector, and identity services as required; this has isolation benefits but costs resources.
- **Managed cloud services:** can simplify operations but conflict with the local-first and no-external-inference requirement, and may expose data outside the PC.

## Networking and persistence

Compose service names are internal DNS names. `frontend-api` connects only Next.js and FastAPI. `api-data` connects FastAPI with the app/vector databases and Ollama. `identity-service` connects the app services with Keycloak. `identity-data` is internal and connects only Keycloak with its database. `smtp` connects Keycloak with Mailpit. Host-published ports are loopback-bound. Named volumes retain data after containers are removed; deleting those volumes is destructive.

## Health and startup

PostgreSQL uses `pg_isready`; pgvector additionally checks that the `vector` extension exists. Mailpit uses its readiness command. Keycloak uses the management readiness endpoint over its in-container TCP socket. Ollama's CLI lists models to confirm its server responds. Keycloak depends on its database and Mailpit health.

## Resource and limitations

Three database containers plus Keycloak and Ollama consume more RAM than a consolidated deployment. Ollama model memory and inference load depend on the downloaded model and host GPU/CPU. Compose resource constraints and GPU access will be evaluated on the actual machine; the current file does not assume NVIDIA support because the GPU vendor is not specified.

The local Docker daemon was unavailable when this foundation was written. Compose syntax validation passed, but container startup, image availability, and health transitions remain unverified on the target PC.

## Revisit when

Use Kubernetes only when multi-host deployment, independent scaling, or cluster-level operations become real requirements. Consider consolidating PostgreSQL for a constrained machine if measured memory pressure outweighs isolation benefits. Any change must update the architecture and limitations docs.
