# ADR-010: Support Hindi and English with a local multilingual path

- **Status:** Accepted requirement; implementation pending
- **Date:** 2026-11-10

## Context

The application must accept Hindi and English questions, support both response languages, and persist language preferences without external inference.

## Problem statement

Provide cross-language retrieval and controlled response language while respecting local hardware and privacy.

## Decision

Use local multilingual embeddings, retain the original question, and set response language independently. Measure Hindi and cross-language behavior before claiming support.

## Alternatives considered

Translate all input to English, maintain separate language indexes, or use a cloud translation/embedding API.

## Reasons for rejecting alternatives

Translation can lose nuance and adds inference calls. Separate indexes complicate routing/storage. Cloud APIs violate local inference constraints.

## Advantages

One shared search index may retrieve across Hindi/English while avoiding external services.

## Disadvantages

Multilingual models vary in Hindi quality, and cross-language retrieval adds evaluation complexity.

## Risks and limitations

No Hindi tests or language preference storage exist yet.

## Consequences

Test all four input/output language combinations and Hindi-document retrieval. See [multilingual-support.md](../multilingual-support.md).

## Conditions for revisiting

Use query translation or language-specific models if evidence shows the shared multilingual path is insufficient.
