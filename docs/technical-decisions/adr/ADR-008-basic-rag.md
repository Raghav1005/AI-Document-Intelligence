# ADR-008: Start with a basic, citation-bearing RAG pipeline

- **Status:** Accepted design; implementation pending
- **Date:** 2026-11-10

## Context

The MVP needs answers grounded in user-selected local documents with source references and multilingual queries.

## Problem statement

Choose a retrieval approach that can be explained, evaluated, and run on limited local hardware.

## Decision

Start with local embeddings, owner/selection-filtered pgvector top-k retrieval, a bounded prompt containing citations, and local generation. State when retrieved evidence is insufficient.

## Alternatives considered

Advanced RAG with query rewriting/hybrid search/reranking and Graph RAG.

## Reasons for rejecting alternatives

Advanced retrieval adds latency and tuning before a baseline dataset exists. Graph RAG adds entity/relationship extraction and maintenance that do not fit the initial document Q&A scope.

## Advantages

Small, observable pipeline and direct source attribution; can add measured retrieval improvements later.

## Disadvantages

Basic vector similarity may miss exact terms or return distractors. Citations do not guarantee claims are correct.

## Risks and limitations

No RAG code, evaluation set, or grounded-answer test currently exists. Prompt injection remains a risk.

## Consequences

Build evaluation data before complex ranking changes; treat retrieved text as untrusted and enforce owner filters. See [rag-pipeline.md](../rag-pipeline.md).

## Conditions for revisiting

Add hybrid search, reranking, or graph methods only when measured failures justify their complexity.
