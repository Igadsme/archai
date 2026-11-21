# PostgreSQL schema

`0001_initial.sql` is the normalized schema artifact for users, credentials, datasets, architectures, checkpoints, search sessions, and experiments. It intentionally stores metadata and URIs rather than model or dataset blobs. Alembic migrations `0001_models`, `0002_experiment_provenance`, and `0003_platform_metadata` provide the runtime migration chain; local development still uses in-process registries when `DATABASE_URL` is unset.
