# Local LLM and Model Runtime Decision

**Status: Ollama selected; chat model and performance remain unverified.** Ollama is configured as a local service with a persistent model volume. The initial chat candidate is `qwen2.5:3b-instruct-q4_K_M`; it is a configurable starting point, not a measured recommendation.

## Runtime comparison

- **Ollama:** simple local model pull/runtime API, model persistence, and approachable local setup. Good for a single-PC MVP; concurrency controls, serving throughput, and GPU behavior need local verification.
- **llama.cpp:** direct GGUF control, quantization options, and CPU/GPU flexibility. Better when low-level tuning, embedding inside a custom process, or packaging control is needed; requires more serving integration.
- **vLLM:** high-throughput batching and GPU serving features. Better for larger CUDA-capable machines and many concurrent users; operational and VRAM needs exceed the target single-PC MVP.
- **Cloud inference:** often stronger models and no local hardware burden; disallowed by the privacy/local inference requirements.

## 4 GB VRAM and RAM trade-offs

The model weights are only part of memory use. The KV cache grows with prompt/context length and concurrent sequences, and runtime overhead also needs memory. Quantization reduces weight storage and can make a model fit, with possible quality loss. If VRAM is insufficient, CPU fallback may allow generation at lower speed. The machine's CPU, total RAM, and GPU vendor are unknown, so actual model fit and latency are not claimed.

## Model management

Configure names through environment variables; the API should check availability and expose a status without triggering downloads silently. Users can switch chat and embedding models, but embedding changes require re-indexing. Model downloads are explicit setup work and persist in the Ollama volume. Runtime prompts and documents stay local.

## Revisit when

Move to llama.cpp for low-level control or vLLM for a suitable GPU and concurrent serving requirements. Reconsider model choice only after measuring load time, peak RAM/VRAM, time to first token, generation rate, and Hindi/English answer quality.
