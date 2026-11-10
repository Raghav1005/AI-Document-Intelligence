# Limitations and Trade-offs

This list describes known constraints and risks. Items are not considered solved until verified against the implementation and target machine.

| Limitation | Why it occurs | MVP impact | Current approach | Long-term option | Status |
|---|---|---|---|---|---|
| Limited VRAM (stated as 4 GB) | Model weights, KV cache, and runtime overhead share GPU memory | Limits model size and concurrency | Start with a small quantized model; allow CPU fallback; measure locally | Larger GPU or smaller distilled model | Expected; not measured |
| CPU inference latency | CPU has less parallel throughput than a suitable GPU | Slow responses, especially with long context | Keep context and concurrency conservative | GPU acceleration or dedicated inference hardware | Expected; not measured |
| Model loading time | Weights are loaded into RAM/VRAM on demand | First response can be delayed | Keep Ollama volume persistent and document warm-up | Keep model resident if resources permit | Expected |
| Embedding latency | Local multilingual embedding on CPU can be slower than hosted GPU inference | Upload and indexing duration grows | Background processing and status reporting | Batch inference or a supported local accelerator | Expected; not measured |
| PDF extraction quality | Scanned pages need OCR; complex layouts disrupt text order | Missing or scrambled source text | Report extraction failures; OCR is a later evaluated feature | Add local OCR and layout-aware parsing | Known class of limitation |
| Retrieval relevance | Chunk size, language, and embedding model affect nearest-neighbor quality | Incorrect or incomplete context | Owner and document filters; citation display; evaluation set needed | Hybrid search, reranking, query rewriting | Not evaluated |
| RAG hallucinations | A generative model can infer beyond retrieved evidence | Incorrect answers remain possible | Require evidence-grounded prompt and insufficient-context behavior | Reranking, answer checks, domain evaluation | Not solved |
| Context window | Long histories and retrieved passages consume finite model context | Older messages or chunks may be omitted | Bound retrieved context and summarize selectively | Larger-context model or context management | Model-dependent |
| Hindi retrieval quality | Multilingual models vary in Hindi coverage and script handling | Hindi questions may retrieve weaker evidence | Choose multilingual embeddings and test Hindi/English cases | Better model, query translation, hybrid retrieval | Not evaluated |
| Compose resource use | Multiple databases, Keycloak, and Ollama compete for local memory | Startup or inference may pressure RAM | Separate services per design; document resource use after measurement | Optional low-resource profile | Not measured |
| Storage growth | Models, uploads, chunks, and database indexes persist | Disk usage accumulates | Named volumes and document deletion | Quotas, retention policies, backup/restore tooling | Planned controls |
| Keycloak operations | Self-hosted identity requires configuration, upgrades, backup, and extension maintenance | More setup than a managed identity service | Keep realm and SMTP setup documented; test health checks | Managed identity only if privacy/locality constraints change | Accepted cost |
| OTP extension risk | Numeric email codes may need a custom Keycloak extension | Extra Java plugin and upgrade surface | Validate extension compatibility before relying on it | Accept built-in verification links if product requirements allow | Pending implementation |
| Streaming disconnects | Browser, proxy, or model can terminate a long-lived response | Partial answer and persistence edge cases | SSE with explicit error and completion events | Resume tokens or WebSockets if needed | Planned |

## Hardware measurements required

Before claiming acceptable local performance, record host CPU, RAM, GPU, available VRAM, model quantization, time to load, time to first token, generation rate, embedding throughput, and peak memory. No performance target is claimed by this baseline.
