-- Normalized schema artifact matching Alembic 0007_research_projects.
-- Alembic is the runtime source of truth; this file documents the table for Docker/Postgres reviews.
CREATE TABLE IF NOT EXISTS research_projects (
    project_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    task VARCHAR(128) NOT NULL,
    dataset_id VARCHAR(128),
    dataset_version VARCHAR(128),
    constraints JSON NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
