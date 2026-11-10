# ADR-004: Use PostgreSQL for application and identity data

- **Status:** Accepted design; application schemas pending
- **Date:** 2026-11-10

## Context

The system stores relational conversations/settings, document metadata and chunks, vector embeddings, and Keycloak identity data. The user requests separate app, vector, and identity database services.

## Problem statement

Select a local relational store with transactions, ownership constraints, and pgvector compatibility.

## Decision

Use PostgreSQL for app data, PostgreSQL with pgvector for document/vector data, and a separate PostgreSQL service controlled by Keycloak.

## Alternatives considered

MySQL, MongoDB, one shared PostgreSQL service, and dedicated vector-only databases.

## Reasons for rejecting alternatives

MySQL is viable for relational records but has less direct pgvector integration. MongoDB is flexible but does not replace the need for vector search or relational integrity. A shared PostgreSQL instance uses fewer resources but weakens requested service separation. Dedicated vector systems remain a future option.

## Advantages

Relational constraints, transactions, mature SQL, and pgvector compatibility.

## Disadvantages

Three database containers add memory, storage, backups, and upgrades. Schema migrations and consistent restores remain to be implemented.

## Risks and limitations

No application tables or migration mechanism exists. Docker startup is unverified due the unavailable local engine.

## Consequences

Use verified Keycloak `sub` as application owner key; keep Keycloak schema managed by Keycloak. See [database.md](../database.md).

## Conditions for revisiting

Consolidate services if measured local resource pressure requires it, or split vector data if pgvector limits are measured.
