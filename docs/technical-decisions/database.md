# Relational Database Decision

**Status: Accepted design; application schema pending.** PostgreSQL stores application relational data. A separate PostgreSQL service with pgvector stores document chunks and embeddings; Keycloak owns a third PostgreSQL service. The Compose services exist, but application tables/migrations do not yet.

## Comparison

- **PostgreSQL:** relational constraints, transactions, JSON support, mature indexing, and pgvector extension compatibility. Strong fit for conversations, settings, metadata filters, and local operation.
- **MySQL:** reliable relational database with broad hosting support; works for application metadata, but pgvector compatibility and the chosen vector integration make it less direct here.
- **MongoDB:** flexible document-oriented schema can fit evolving records, but messages, ownership relations, and conversation/document associations benefit from relational constraints. It would not remove the need for a vector search design.

## Why separate the data stores

App data and identity have different lifecycle/access needs. Vector data has embedding indexes and large chunk payloads; separating it bounds operational coupling and follows the requested isolation. The trade-off is more memory, disk, backups, and monitoring. One PostgreSQL service with multiple databases could be a better fit if measured PC memory is too constrained.

## Planned data model

The application DB will store user preferences keyed to Keycloak `sub`, conversations, messages, and selections. Vector DB will store documents, content hashes, extraction status, chunks, owner IDs, metadata, and embeddings. Keycloak DB remains Keycloak-managed. Ownership always comes from verified JWT claims.

## Performance and risks

Indexes and transactions support correctness; long message histories and embeddings grow storage. Backups must cover all persistent volumes consistently. Migration and restore procedures are not implemented yet.

## Revisit when

Consolidate PostgreSQL if local memory pressure is measured and isolation can be retained through roles/schemas. Separate a dedicated vector service if search scale or filtering/index needs outgrow pgvector. Reference: [docker-compose.yml](../../docker-compose.yml).
