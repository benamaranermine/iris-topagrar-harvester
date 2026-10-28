CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS iris_staging;

CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'topagrar',
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    source_url TEXT NOT NULL,
    summary TEXT,
    signal_type TEXT,
    location_text TEXT,
    geom geometry(Point, 25832),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT signal_ingest_source_id_unique UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS signal_ingest_published_at_idx
    ON iris_staging.signal_ingest (published_at);

CREATE INDEX IF NOT EXISTS signal_ingest_signal_type_idx
    ON iris_staging.signal_ingest (signal_type);

CREATE INDEX IF NOT EXISTS signal_ingest_geom_idx
    ON iris_staging.signal_ingest USING GIST (geom);