# ADR-006: Use local multilingual embeddings

- **Status:** Candidate accepted for evaluation; implementation pending
- **Date:** 2026-11-10

## Context

The product must support Hindi and English, including cross-language queries, while keeping inference local.

## Problem statement

Select a local embedding path that can compare Hindi and English text without sending documents or queries to an external API.

## Decision

Use a configurable local embedding model through Ollama initially; `embeddinggemma:latest` is the candidate in `.env.example`. Evaluate retrieval quality before calling it selected for production.

## Alternatives considered

Sentence Transformers, Ollama embedding models, and cloud embedding APIs.

## Reasons for rejecting alternatives

Sentence Transformers remains viable but adds model loading/runtime integration to Python. Ollama reuses the local model runtime. Cloud APIs conflict with the no-external-inference requirement.

## Advantages

One local inference boundary and multilingual candidate support.

## Disadvantages

Embedding latency, memory, dimensional storage, and Hindi quality are unknown. Changing models requires full re-indexing.

## Risks and limitations

No model has been pulled or measured. The target hardware and Hindi benchmark are not yet available.

## Consequences

Persist model/version and dimensions with the vector index; add cross-language retrieval tests. See [embeddings.md](../embeddings.md).

## Conditions for revisiting

Change to BGE-M3, a Sentence Transformers checkpoint, or another local model if measurable Hindi/English quality or latency is inadequate.
