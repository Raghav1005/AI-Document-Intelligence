# ADR-009: Use Docker Compose for the local service stack

- **Status:** Accepted for the local MVP
- **Date:** 2026-11-10

## Context

The system must run on one local PC and includes multiple independently configured services with persistent state. The user requires a single monorepo and Docker-based local orchestration.

## Problem statement

We need reproducible startup, private service networking, health-aware dependencies, and persistent databases/models without imposing cluster administration on a local developer.

## Decision

Define the initial stack in the root `docker-compose.yml`. Use separate app, vector, and Keycloak PostgreSQL services, plus Keycloak, Mailpit, and Ollama. Bind host-facing ports to loopback and use named volumes.

## Alternatives considered

- Kubernetes for orchestration.
- Directly installing services on the host.
- A single PostgreSQL service with separate databases.
- Hosted database, authentication, or inference services.

## Reasons for rejecting alternatives

Kubernetes adds cluster operations that the single-PC MVP does not need. Host installs reduce repeatability. A unified database reduces resource consumption but weakens the requested service separation. Hosted inference/auth/data services conflict with the local-first requirement or increase data exposure.

## Advantages

- Declarative local service topology.
- Service-name networking and health dependencies.
- Named volume persistence.
- Loopback-bound ports by default.

## Disadvantages

- Multiple databases consume more RAM and disk.
- Docker Desktop must be installed and running.
- GPU acceleration varies by host and is not configured by default.
- Compose is not a multi-host production orchestrator.

## Risks and limitations

Compose configuration has been validated, but containers have not been started because the Docker Desktop Linux engine was unavailable in the implementation environment. Local startup and health transitions remain unverified.

## Consequences

The stack is easy to run on one machine but requires documented secrets, model downloads, volume management, and resource measurement. The implementation and rationale are in [docker-compose.yml](../../../docker-compose.yml) and [docker-and-deployment.md](../docker-and-deployment.md).

## Conditions for revisiting

Revisit if the user targets a multi-host deployment, needs independent service scaling, experiences measured resource pressure, or changes the local-only data/inference requirement.
