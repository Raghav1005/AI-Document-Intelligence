# Multilingual Support Decision

**Status: Hindi and English are product requirements; implementation pending.** The current shell identifies both languages as planned but has no selector or language-aware service behavior.

## Design

Persist preferred response language per user. Query language and response language are separate: Hindi input may request Hindi or English output. Use multilingual embeddings for shared Hindi/English retrieval, preserve the original question, and include a clear response-language instruction in the generation request.

## Alternatives and trade-offs

- **Multilingual embeddings:** one model can map cross-language texts into a shared vector space; quality and memory vary by language.
- **Translate-then-search:** can normalize queries to one language but adds model calls and translation errors, and may lose named-entity nuance.
- **Language-specific indexes/models:** can improve domain performance, but complicate routing and storage and risk inconsistent retrieval.
- **Cloud translation/embeddings:** may be high quality, but violates local-only inference and document privacy.

## Testing needed

Test Hindi→Hindi, English→English, Hindi→English, and English→Hindi, plus Hindi documents and mixed-script terms. Score retrieval and answer faithfulness separately. Model names alone do not establish language quality.

## Revisit when

Use translation, language-specific embeddings, or another model only if evaluations show gaps and local hardware can support the extra inference cost.
