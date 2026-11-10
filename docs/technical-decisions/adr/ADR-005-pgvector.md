# ADR-005: Use pgvector for the local vector index

- **Status:** Accepted design; retrieval pending
- **Date:** 2026-11-10

## Context

The MVP needs local similarity search with document/owner metadata filtering and a single-PC deployment.

## Problem statement

Choose an embedding store that supports local persistence and secure owner-scoped retrieval without a large distributed service stack.

## Decision

Use the PostgreSQL pgvector extension in a separate vector database service.

## Alternatives considered

Qdrant, Milvus, ChromaDB, and FAISS.

## Reasons for rejecting alternatives

Qdrant and Milvus are strong dedicated vector services but add another technology and operational surface before scale requires it. ChromaDB is effective for prototyping but PostgreSQL is preferred as the authoritative store. FAISS is a library and does not provide persistent multi-user metadata/transactions alone.

## Advantages

SQL metadata filters and vectors share one service; local persistence and Compose operation are straightforward.

## Disadvantages

Index performance and recall depend on tuning; large-scale distributed vector throughput is not its goal.

## Risks and limitations

Extension is initialized but no schema/index/query exists. Retrieval accuracy is unmeasured.

## Consequences

Define retriever interface and benchmark filtered top-k search. See [vector-database.md](../vector-database.md).

## Conditions for revisiting

Move to Qdrant/Milvus if corpus size, query throughput, or filtering/index needs exceed measured pgvector capacity.
