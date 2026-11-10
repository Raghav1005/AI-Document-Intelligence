# ADR-007: Use Ollama for local model serving

- **Status:** Accepted for the local MVP; model performance pending
- **Date:** 2026-11-10

## Context

All inference must be local. The target machine is described as having 4 GB VRAM and limited system RAM.

## Problem statement

Choose a local runtime with manageable model downloads and an API suitable for chat and embeddings.

## Decision

Use Ollama as a persistent-volume container. Configure chat and embedding model names through environment variables. Start with a small quantized chat candidate, but verify fit and speed on the actual machine.

## Alternatives considered

llama.cpp, vLLM, and external cloud inference.

## Reasons for rejecting alternatives

llama.cpp offers more tuning but more integration work. vLLM is optimized for GPU serving/concurrency beyond this single-PC MVP. Cloud inference violates local privacy requirements.

## Advantages

Simple local model-management API, model cache volume, and one inference service boundary.

## Disadvantages

Throughput, batching, memory use, and GPU behavior are host-dependent. Model/context/concurrency settings can exceed 4 GB VRAM.

## Risks and limitations

The service has not started in this environment, and candidate model memory/performance are not measured.

## Consequences

Model pulls are explicit setup steps; runtime code must check availability and report local errors. See [llm-and-models.md](../llm-and-models.md).

## Conditions for revisiting

Use llama.cpp for tighter control or vLLM for an adequately provisioned multi-user GPU server if measured needs justify the switch.
