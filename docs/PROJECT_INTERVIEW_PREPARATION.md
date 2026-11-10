# Project Interview Preparation

**Status:** The answers distinguish implemented authentication from planned document processing, RAG, and chat. The live Keycloak/Docker flow has not been verified yet.

## 1. Architecture and design decisions

### Why a monorepo?

**Short answer:** The app is one locally deployed product with coordinated frontend, API, infrastructure, and docs.

**Detailed explanation:** One repository lets a feature PR update the UI, API, database, and documentation together while preserving one Compose setup. The trade-off is a larger repository and the need for CI to scope checks by component.

**Project example:** `frontend/`, `backend/`, `infrastructure/`, and Compose are under the same root.

**Follow-ups:** How would ownership scale across teams? Which checks should run on documentation-only changes?

## 2. Frontend and backend communication

### Why Next.js instead of plain React?

**Short answer:** Next.js provides the required React App Router and standalone deployment target for this UI.

**Detailed explanation:** Plain React with Vite could serve a client-only SPA with less server framework, but this project specifies Next.js and standalone output. SSR does not replace authorization or make local inference faster.

**Project example:** `frontend/app/page.tsx` shows a Keycloak sign-in/registration view and gates the workspace on authenticated status.

**Follow-ups:** Which routes need client rendering? How will SSE be handled if it is later proxied through Next.js?

### How will React communicate with FastAPI?

**Short answer:** The browser calls FastAPI on `localhost:8000` with an in-memory Keycloak bearer token.

**Detailed explanation:** The public OIDC client uses PKCE S256, keeps tokens in memory, and refreshes before expiry. FastAPI remains the authorization boundary and validates the token itself. The trade-off is that page JavaScript can access in-memory tokens.

**Project example:** Compose publishes port 8000 to loopback and CORS allows the Next.js origin `http://localhost:3000`.

**Follow-ups:** How do you reduce XSS risk? How will SSE reconnect/cancel behavior be handled?

## 3. Docker and containerization

### Why Docker Compose instead of Kubernetes?

**Short answer:** Compose meets the one-PC development/deployment scope with less operational overhead.

**Detailed explanation:** It provides service DNS, networks, health dependencies, and named volumes. Kubernetes becomes better when multi-host scheduling, independent scaling, and cluster operations are required.

**Project example:** Compose defines six infrastructure services plus frontend and backend, with database and model volumes.

**Follow-ups:** How will upgrades and backups work? Which volumes can be safely deleted?

## 4. Authentication and JWT

### How will FastAPI know a JWT is genuine?

**Short answer:** It verifies the RS256 signature against Keycloak JWKS and validates issuer, expiry, subject, and authorized client (`azp`). An optional audience claim can also be required.

**Detailed explanation:** JWT payloads are encoded, not secret. Signature verification binds claims to Keycloak's signing key; issuer/audience limit token origin and intended service; expiry limits token lifetime. The backend must reject invalid tokens even if the frontend has checked them.

**Project example:** `backend/app/auth/keycloak.py` verifies access tokens; tests create signed RSA tokens and mock the JWKS key lookup.

**Follow-ups:** What is JWKS key rotation? How should the API behave during Keycloak downtime?

### Why Keycloak instead of custom JWT authentication?

**Short answer:** Keycloak owns identity lifecycle, OIDC, sessions, roles, and account recovery; implementing those securely would expand the app's risk and scope.

**Detailed explanation:** Self-hosting provides local control and avoids a managed identity dependency, but adds database, upgrade, realm, and extension operations. A managed provider can be better when the product accepts cloud identity and values reduced operations.

**Project example:** The configured realm/client are `local-ai` and `local-ai-frontend`; frontend integration exists, but live login still needs Docker verification.

**Follow-ups:** What happens if Keycloak is unavailable? Why might numeric OTP need a custom extension?

## 5. Keycloak and OTP

### Does default Keycloak email verification satisfy numeric OTP?

**Short answer:** Not necessarily; standard verification is commonly link-based. Numeric codes need a Keycloak authenticator/required-action extension or a requirement change.

**Detailed explanation:** A code flow needs expiry, attempt counters, resend throttling, safe code storage, and upgrade tests. Mailpit captures development email but is not an OTP implementation.

**Project example:** Mailpit and Keycloak services are configured; there is no realm, SMTP test, or OTP extension yet.

**Follow-ups:** How is brute force limited? How are extensions versioned with Keycloak?

## 6. PostgreSQL and pgvector

### Why separate vector data from application data?

**Short answer:** It separates document/vector workload and access from conversations and identity while keeping vector search in PostgreSQL.

**Detailed explanation:** pgvector allows SQL filters and nearest-neighbor search together, but multiple PostgreSQL services cost more RAM and operational effort. A single database with separate schemas/databases could be better on a very constrained PC.

**Project example:** Compose has separate `app-db`, `vector-db`, and `keycloak-db`; only the extension initialization exists so far.

**Follow-ups:** When would Qdrant or Milvus be better? What indexes and distance operators will be evaluated?

## 7. Embeddings and vector similarity

### What does an embedding represent, and why can similarity be wrong?

**Short answer:** An embedding maps text to a numeric vector whose geometry captures learned semantic patterns; nearest vectors are candidates, not proof of relevance.

**Detailed explanation:** Cosine similarity compares vector directions. Model domain, language, chunking, and query wording affect rankings. Test retrieval with representative questions and citations before claiming accuracy.

**Project example:** The chosen multilingual model is configured as a candidate only; no vectors or retrieval results have been measured.

**Follow-ups:** What is the vector dimension? How will embedding model changes trigger re-indexing?

## 8. Document processing

### How will the system process a large PDF?

**Short answer:** Validate and persist upload metadata, enqueue work, extract text, chunk it, embed locally, and report status asynchronously.

**Detailed explanation:** Background processing keeps upload requests responsive and makes failures visible. Scanned documents need OCR; tables and layout may be lost in plain text extraction. Current code has no upload pipeline.

**Project example:** No document endpoint or parser is present yet.

**Follow-ups:** How are duplicates detected? How are retries and deletions handled?

## 9. RAG and retrieval

### Why retrieve chunks instead of whole documents?

**Short answer:** Chunks provide focused evidence and fit a bounded context window; whole documents dilute relevance and may exceed model limits.

**Detailed explanation:** Chunking size and overlap trade recall, precision, embedding cost, and prompt size. Similarity retrieval can be extended with hybrid search and reranking when evaluation shows a need.

**Project example:** The RAG pipeline is planned only; no retriever or citations exist yet.

**Follow-ups:** How is top-k chosen? How are prompt injections in references treated?

## 10. Local LLM inference

### What if the local model does not fit into GPU memory?

**Short answer:** Use a smaller quantized model, reduce context/concurrency, or fall back to CPU with an acknowledged latency cost.

**Detailed explanation:** Weight size is only part of memory use; the context KV cache and runtime overhead also consume memory. Quantization saves memory but can reduce answer quality. The target machine has a stated 4 GB VRAM constraint, but its RAM and CPU are not yet measured.

**Project example:** Ollama is containerized with persistent model storage; no model is pulled or benchmarked.

**Follow-ups:** How will time-to-first-token be measured? How do you prevent multiple requests from exhausting memory?

## 11. Multilingual support

### How will Hindi questions retrieve English documents?

**Short answer:** Use multilingual embeddings and test cross-language retrieval; response language is selected separately from query language.

**Detailed explanation:** A language selector does not provide cross-language semantic alignment by itself. Hindi script, code switching, translation quality, and model response ability need explicit evaluation.

**Project example:** The UI labels Hindi/English as planned and `embeddinggemma` is a candidate model; behavior is not implemented or tested.

**Follow-ups:** Would query translation help? How will Hindi retrieval quality be measured?

## 12. Security

### How do you prevent a user from accessing another user's documents?

**Short answer:** Derive the owner from the verified JWT and scope every document, chunk, conversation, and deletion query to that owner.

**Detailed explanation:** Frontend filtering is not a security boundary. Service-layer ownership filters, database constraints, and cross-user integration tests are required.

**Project example:** No ownership model or protected route exists yet; the schema and authorization are planned.

**Follow-ups:** How are identifiers handled in delete/reprocess routes? What is the breach impact of a missing owner filter?

### How do you handle prompt injection in uploaded files?

**Short answer:** Treat retrieved text as untrusted evidence, isolate it from system instructions, avoid granting it tool access, and evaluate adversarial documents.

**Detailed explanation:** Prompt wording alone cannot guarantee that a model ignores malicious content. The system should not expose secrets or privileged tools to retrieved passages and should require citations for claims.

**Project example:** Prompt construction is not implemented yet.

**Follow-ups:** Can citations still be manipulated? How would you test injection resistance?

## 13. Performance and optimization

### How would you scale this to 10,000 users?

**Short answer:** First measure and separate bottlenecks; then use dedicated worker capacity, a production database/vector strategy, observability, and horizontally scalable API/model serving.

**Detailed explanation:** A single-PC Compose stack is not a 10,000-user production design. Ollama single-host inference, PostgreSQL contention, queue throughput, storage, and identity availability each need separate capacity plans. Kubernetes might become useful after services are independently deployable and measurable.

**Project example:** This app is designed for a local PC and has no load measurements.

**Follow-ups:** Which service would you scale first? What data isolation model would you retain?

## 14. Limitations and future improvements

### What would you change with more hardware?

**Short answer:** Benchmark a stronger multilingual embedding model and chat model, then increase context/concurrency only where quality and latency measurements justify it.

**Detailed explanation:** Additional VRAM can improve model fit and throughput, but does not automatically solve retrieval quality, extraction errors, or prompt injection. Model and index changes require migration/re-indexing plans.

**Project example:** The current 4 GB VRAM limit is documented in [LIMITATIONS_AND_TRADEOFFS.md](LIMITATIONS_AND_TRADEOFFS.md), with performance still unmeasured.

**Follow-ups:** What are your acceptance targets? What regression dataset will protect Hindi retrieval quality?
