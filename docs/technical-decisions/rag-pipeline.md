# RAG Pipeline Decision

**Status: Basic RAG selected for the MVP; no pipeline is implemented yet.** The planned flow uses local query embeddings, pgvector retrieval filtered by owner and selected documents, a bounded context prompt, local Ollama generation, citations, and SSE streaming.

## Comparison

- **Basic RAG:** embed query, retrieve similar chunks, generate from them. Simple and explainable for the first iteration, but ranking and context quality can be weak.
- **Advanced RAG:** query rewriting, hybrid keyword/vector retrieval, metadata-aware filtering, reranking, and iterative retrieval can improve recall/precision; each adds latency and evaluation/maintenance work.
- **Graph RAG:** models entities and relationships for multi-hop questions; useful for knowledge graph workloads, but adds extraction and graph maintenance beyond a first local MVP.

## Chunking

Fixed-size chunks are easy to bound and index, but may split a heading/table or mix topics. Semantic/structure-aware chunks preserve headings, paragraphs, and page structure better, but extraction is format-dependent. Start with structure-aware boundaries plus a measured size and overlap, then compare retrieval results.

## Similarity and hybrid search

Vector similarity finds semantic candidates but may miss exact names, IDs, or numbers. Hybrid search combines lexical matching (for example full-text search) and vectors; it can help exact terms but requires rank fusion and tuning. Reranking uses a second model to reorder candidates, improving precision at extra compute/latency cost.

## Security and grounding

Every retrieval query must filter by authenticated owner and the conversation's selected document set before prompt construction. Retrieved text is untrusted. The answer should cite source document/page/chunk references and state when evidence is insufficient. This reduces, but does not eliminate, hallucinations or prompt injection.

## Evaluation

Measure Recall@k, citation correctness, grounded-answer rate, and Hindi/English cross-language retrieval on a small representative set before adopting a more complex retriever. No such evaluation exists yet.
