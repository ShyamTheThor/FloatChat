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
    lat               DOUBLE PRECISION NOT NULL,
    lon               DOUBLE PRECISION NOT NULL,
    timestamp         TIMESTAMPTZ      NOT NULL,

    -- Vertical coordinate (one row per depth level)
    pressure_dbar     REAL,            -- raw sensor output, decibars
    depth_m           REAL,            -- derived: pressure × latitude correction

    -- Core ocean measurements (NULL = missing / bad-QC level)
    temperature       REAL,            -- in-situ, degree_Celsius
    salinity          REAL,            -- Practical Salinity, psu

    -- Provenance / metadata (optional)
    basin             INTEGER,         -- Argovis basin code (3=Indian Ocean)
    profile_direction CHAR(1),         -- A=ascending, D=descending
    data_mode         CHAR(1),         -- R=real-time, A=adjusted, D=delayed-mode
    source_url        TEXT,            -- original NetCDF URL on GDAC/INCOIS

    -- Uniqueness: one row per (float, cycle, pressure level)
    -- NULLS are distinct in SQL UNIQUE, so use a partial unique index instead
    CONSTRAINT uq_profile_level UNIQUE (float_id, cycle_number, pressure_dbar)
);

-- Indexes for the three primary query patterns (region, date range, depth band)
CREATE INDEX IF NOT EXISTS idx_float_id  ON argo_profiles (float_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON argo_profiles (timestamp);
CREATE INDEX IF NOT EXISTS idx_lat_lon   ON argo_profiles (lat, lon);
CREATE INDEX IF NOT EXISTS idx_depth     ON argo_profiles (depth_m);
