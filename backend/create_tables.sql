-- backend/create_tables.sql
-- DDL for the FloatChat ARGO pipeline.
-- Run via: backend/db.py::create_tables()  or  psql -f backend/create_tables.sql
-- Safe to re-run: all statements use IF NOT EXISTS / CREATE OR REPLACE.

CREATE TABLE IF NOT EXISTS argo_profiles (
    id                BIGSERIAL        PRIMARY KEY,

    -- Identity
    float_id          VARCHAR(20)      NOT NULL,
    cycle_number      INTEGER,                   -- nullable: some Argovis _ids lack a parseable cycle

    -- Position & time (required — rows without these are not loaded)
    lat               DOUBLE PRECISION NOT NULL CONSTRAINT chk_lat CHECK (lat BETWEEN -90.0 AND 90.0),
    lon               DOUBLE PRECISION NOT NULL CONSTRAINT chk_lon CHECK (lon BETWEEN -180.0 AND 180.0),
    timestamp         TIMESTAMPTZ      NOT NULL,

    -- Vertical coordinate (one row per depth level)
    pressure_dbar     REAL             CONSTRAINT chk_pressure CHECK (pressure_dbar IS NULL OR pressure_dbar >= 0.0),
    depth_m           REAL             CONSTRAINT chk_depth CHECK (depth_m IS NULL OR depth_m >= 0.0),

    -- Core ocean measurements (NULL = missing / bad-QC level)
    temperature       REAL             CONSTRAINT chk_temp CHECK (temperature IS NULL OR (temperature >= -2.5 AND temperature <= 40.0)),
    salinity          REAL             CONSTRAINT chk_sal CHECK (salinity IS NULL OR (salinity >= 0.0 AND salinity <= 45.0)),

    -- Provenance / metadata (optional)
    basin             INTEGER,         -- Argovis basin code (3=Indian Ocean)
    profile_direction CHAR(1),         -- A=ascending, D=descending
    data_mode         CHAR(1),         -- R=real-time, A=adjusted, D=delayed-mode
    source_url        TEXT             -- original NetCDF URL on GDAC/INCOIS
);

-- Unique index for idempotent ETL using float_id, timestamp, and COALESCE pressure_dbar
-- (timestamp is unique per surfacing cycle, handling floats even when cycle_number is NULL)
CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_profile_level 
    ON argo_profiles (float_id, timestamp, COALESCE(pressure_dbar, -1.0));

-- Indexes for spatial, temporal, and depth query patterns
CREATE INDEX IF NOT EXISTS idx_float_id         ON argo_profiles (float_id);
CREATE INDEX IF NOT EXISTS idx_timestamp        ON argo_profiles (timestamp);
CREATE INDEX IF NOT EXISTS idx_lat_lon          ON argo_profiles (lat, lon);
CREATE INDEX IF NOT EXISTS idx_depth            ON argo_profiles (depth_m);
CREATE INDEX IF NOT EXISTS idx_spatial_temporal ON argo_profiles (lat, lon, timestamp);
CREATE INDEX IF NOT EXISTS idx_profile_depth    ON argo_profiles (float_id, cycle_number, depth_m);

