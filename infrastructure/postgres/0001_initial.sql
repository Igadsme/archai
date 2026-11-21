-- ArchAI relational schema. Large checkpoints/datasets stay in artifact storage.
CREATE TABLE IF NOT EXISTS users (
  user_id UUID PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_credentials (
  credential_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  key_hash TEXT NOT NULL UNIQUE,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
  dataset_id TEXT NOT NULL,
  version TEXT NOT NULL,
  checksum TEXT NOT NULL,
  uri TEXT NOT NULL,
  license TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (dataset_id, version)
);

CREATE TABLE IF NOT EXISTS architectures (
  architecture_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  search_space TEXT NOT NULL,
  canonical_json JSONB NOT NULL,
  generator_version TEXT NOT NULL,
  seed INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_checkpoints (
  checkpoint_id UUID PRIMARY KEY,
  model_id TEXT NOT NULL,
  model_kind TEXT NOT NULL CHECK (model_kind IN ('generator', 'predictor', 'candidate')),
  version TEXT NOT NULL,
  artifact_uri TEXT NOT NULL,
  checksum TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, version)
);

CREATE TABLE IF NOT EXISTS search_sessions (
  search_id UUID PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('created', 'running', 'paused', 'completed', 'cancelled', 'failed')),
  algorithm TEXT NOT NULL,
  config JSONB NOT NULL,
  budget_evaluations INTEGER NOT NULL CHECK (budget_evaluations > 0),
  consumed_evaluations INTEGER NOT NULL DEFAULT 0 CHECK (consumed_evaluations >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
  experiment_id UUID PRIMARY KEY,
  search_id UUID REFERENCES search_sessions(search_id) ON DELETE SET NULL,
  architecture_id TEXT NOT NULL REFERENCES architectures(architecture_id),
  checkpoint_id UUID REFERENCES model_checkpoints(checkpoint_id),
  dataset_id TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  evidence_type TEXT NOT NULL CHECK (evidence_type IN ('predicted', 'benchmark_lookup', 'measured_training')),
  status TEXT NOT NULL CHECK (status IN ('created', 'running', 'completed', 'failed', 'cancelled')),
  seed INTEGER NOT NULL,
  hardware JSONB NOT NULL DEFAULT '{}',
  metrics JSONB NOT NULL DEFAULT '{}',
  failure_detail TEXT,
  provenance JSONB NOT NULL DEFAULT '{}',
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS experiments_architecture_idx ON experiments(architecture_id);
CREATE INDEX IF NOT EXISTS experiments_status_idx ON experiments(status);
CREATE INDEX IF NOT EXISTS experiments_search_idx ON experiments(search_id);
