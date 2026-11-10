# Embeddings Decision

**Status: Candidate selected for the local MVP; retrieval quality pending evaluation.** `.env.example` sets `embeddinggemma:latest` as the initial Ollama model candidate. No model has been downloaded or benchmarked, and no vectors are stored yet.

## Comparison

- **Sentence Transformers:** broad model catalog and direct Python integration; suitable when choosing a specific multilingual checkpoint and embedding in the worker. Adds Python model dependencies and model storage separate from Ollama.
- **Ollama embeddings:** one local runtime API for both generation and embeddings, with persistent model storage. Simpler service topology, but model choice, versioning, and throughput depend on Ollama support.
- **Cloud embedding APIs:** often high quality and easy to scale; rejected because document text and queries would leave the PC and require an external inference service.

## Why multilingual embeddings

English and Hindi queries/documents need a shared semantic space for cross-language retrieval. The candidate `embeddinggemma` family is advertised as multilingual, but Hindi retrieval must be tested against the intended document types. If results are poor, evaluate BGE-M3 or a Sentence Transformers checkpoint. Selection must account for dimensions, latency, storage, licensing, and measured quality.

## How dimensions and cosine similarity work

An embedding with dimension *d* is a length-*d* vector of learned numeric features. Cosine similarity is the dot product divided by both vector magnitudes and compares direction, usually from -1 to 1. A higher score indicates geometric proximity, not factual support. Dimensions affect index storage and compute: for N vectors, raw float32 storage is approximately `N × d × 4` bytes before metadata and index overhead.

## Trade-offs and model changes

Higher quality or broader language coverage may require more memory and CPU time. Quantization can lower memory at some quality cost. The selected embedding model and dimension must be recorded with each index; switching models requires re-embedding all stored chunks, not mixing vectors from incompatible spaces.

References: model setting in [.env.example](../../.env.example) and [Ollama](../../docker-compose.yml).
