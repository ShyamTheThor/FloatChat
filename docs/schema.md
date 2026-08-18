# Schema Definition — FloatChat ARGO Pipeline

> Version: 1.0 | Phase 0 output | 2026-08-17

This document defines the **target clean schema** for the `argo_profiles` table
in PostgreSQL. This schema is what the AI/ML teammate will query from the RAG layer.

---

## Target Table: `argo_profiles`

One row = one observation at one depth level from one float cycle.

### Core Fields (required, always populated)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGSERIAL` | PRIMARY KEY | Internal surrogate key |
| `float_id` | `VARCHAR(20)` | NOT NULL, INDEXED | ARGO platform ID (e.g. `"2902275"`) |
| `cycle_number` | `INTEGER` | nullable | Dive cycle number — nullable because some Argovis `_id` fields lack a parseable cycle |
| `lat` | `DOUBLE PRECISION` | NOT NULL, CHECK −90…90 | Latitude in decimal degrees (N positive) |
| `lon` | `DOUBLE PRECISION` | NOT NULL, CHECK −180…180 | Longitude in decimal degrees (E positive) |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL, INDEXED | UTC datetime of profile observation |
| `pressure_dbar` | `REAL` | CHECK ≥ 0 | Pressure in decibars at this level (≈depth in m) |
| `depth_m` | `REAL` | — | Depth in metres, derived from pressure + latitude |
| `temperature` | `REAL` | — | In-situ temperature in °C (NULL if bad/missing) |
| `salinity` | `REAL` | — | Practical salinity in psu (NULL if bad/missing) |

> `temperature`, `salinity`, `pressure_dbar`, `depth_m` are nullable at the row level
> because null levels exist in real Argo data (sensor gaps, QC failures).
> The pipeline stores them as NULL rather than dropping the row, preserving lineage.

### Uniqueness Constraint

Uses COALESCE sentinel values to handle NULLs (PostgreSQL `UNIQUE` treats NULLs as distinct):

```sql
CREATE UNIQUE INDEX idx_uq_profile_level
    ON argo_profiles (float_id, COALESCE(cycle_number, -1), COALESCE(pressure_dbar, -1.0));
```

This allows safe re-runs (`ON CONFLICT DO NOTHING`) without duplicate rows, even when `cycle_number` or `pressure_dbar` are NULL.

---

### Optional / Nice-to-Have Fields

These are stored in the table but may be NULL for some sources.

| Column | Type | Description | Value |
|---|---|---|---|
| `basin` | `INTEGER` | Argovis ocean basin code | 3=Indian Ocean, 56=Bay of Bengal |
| `profile_direction` | `CHAR(1)` | Float movement direction | `A`=ascending, `D`=descending |
| `data_mode` | `CHAR(1)` | Data quality mode | `R`=real-time, `A`=adjusted, `D`=delayed |
| `source_url` | `TEXT` | URL of source NetCDF file on GDAC | e.g. `ftp://ftp.ifremer.fr/…` |

---

## Indexes

| Index Name | Columns | Rationale |
|---|---|---|
| `idx_float_id` | `float_id` | Look up all cycles for a float |
| `idx_timestamp` | `timestamp` | Date range queries (most common) |
| `idx_lat_lon` | `(lat, lon)` | Regional bounding-box queries |
| `idx_depth` | `depth_m` | Depth band queries |

> **Note for Phase 2**: Consider adding a PostGIS `GEOGRAPHY` column for proper
> geospatial indexing if query volumes grow. For Phase 0/1 the composite
> `(lat, lon)` B-tree index is sufficient.

---

## Full SQL DDL

See [create_tables.sql](file:///Users/apple/Desktop/OCEAN/backend/create_tables.sql) for the authoritative DDL.
Key features: CHECK constraints on coordinates/measurements, COALESCE-based unique index,
and composite indexes for spatial/temporal/depth queries.

---

## Physical Range Validation Thresholds

Used in `backend/validate.py` to flag suspicious rows:

| Field | Min | Max | Notes |
|---|---|---|---|
| `temperature` | −2.0 °C | 35.0 °C | Ocean SST never exceeds 35°C; freezing point ≈ −2°C |
| `salinity` | 0.0 psu | 42.0 psu | 0 = freshwater; Red Sea max ≈ 42 |
| `pressure_dbar` | 0 | 7000 | Deepest ARGO floats reach ~6000 dbar |
| `lat` | −90.0 | 90.0 | Geographic constraint |
| `lon` | −180.0 | 180.0 | Geographic constraint |

---

## Phase 2+ Extension Notes

These fields are **not** in the Phase 0/1 schema but are worth adding in later phases:

| Future Field | Reason |
|---|---|
| `oxygen_umol_kg` | BGC-Argo floats measure dissolved oxygen |
| `chlorophyll_mg_m3` | BGC-Argo bio-optical sensor |
| `nitrate_umol_kg` | BGC-Argo chemical sensor |
| `geom GEOGRAPHY(Point,4326)` | PostGIS for proper spatial queries |
| `loaded_at TIMESTAMPTZ` | Audit field for ETL runs |

---

*See also: [data_dictionary.md](./data_dictionary.md) for field-level source mapping.*
