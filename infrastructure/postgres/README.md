# PostgreSQL schema

`0001_initial.sql` is the first normalized schema artifact for users, credentials, datasets, architectures, checkpoints, search sessions, and experiments. It intentionally stores metadata and URIs rather than model or dataset blobs. The runtime API currently uses an in-process registry for local development; wiring this migration through Alembic and a transactional worker service is still pending.
