# FloatChat — ARGO Ocean Data Pipeline

> **SIH25040 | Ministry of Earth Sciences**  
> AI-Powered Conversational Interface for ARGO Ocean Float Data  
> **Phase 0 & 1**: Setup · Data Pipeline · PostgreSQL Storage

---

## Table of Contents
1. [What This Does](#what-this-does)
2. [Prerequisites](#prerequisites)
3. [Quick Start (under 10 minutes)](#quick-start)
4. [Project Structure](#project-structure)
5. [Running the Pipeline](#running-the-pipeline)
6. [Running Queries](#running-queries)
7. [For the AI/ML Teammate (RAG Layer)](#for-the-aiml-teammate-rag-layer)
8. [Data Source Notes](#data-source-notes)
9. [Schema Reference](#schema-reference)

---

## What This Does

This repository fetches real ARGO ocean float profiles from the **Argovis REST API**,
parses them into a clean schema, validates them against physical oceanographic ranges,
and loads them into a local **PostgreSQL** database.

Three query functions (`query_by_region`, `query_by_date_range`, `query_by_depth_band`)
are ready for the RAG/AI layer to call.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org](https://python.org) |
| Docker + Docker Compose | any recent | [docker.com](https://docker.com) |
| Git | any | included on most systems |

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd OCEAN

# 2. Set up Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Copy environment config (edit if you change ports/passwords)
cp .env.example .env

# 5. Start PostgreSQL (runs in background)
docker compose up -d

# 6. Wait ~5 seconds for Postgres to be ready, then fetch sample data
python scripts/fetch_sample_data.py --days 7

# 7. Inspect the data structure (optional but recommended)
python scripts/inspect_data.py

# 8. Run the ETL — parse, validate, and load into DB
python -m backend.load_data

# 9. Verify with a sample query
python backend/queries.py
```

Total time: **~5–8 minutes** (mostly waiting for the Argovis API and Docker pull).

---

## Project Structure

```
OCEAN/
├── .env.example              # Copy to .env — DB credentials
├── .gitignore
├── docker-compose.yml        # Local PostgreSQL 15
├── pyproject.toml            # Python dependencies
├── README.md
│
├── data/
│   ├── raw/                  # Raw Argovis JSON files (gitignored)
│   └── sample/               # Small curated samples (committed)
│
├── backend/
│   ├── __init__.py
│   ├── create_tables.sql     # PostgreSQL DDL
│   ├── db.py                 # Connection + upsert helpers
│   ├── parser.py             # Argovis JSON → clean rows
│   ├── validate.py           # Physical range checks
│   ├── load_data.py          # ETL orchestrator (CLI entry point)
│   └── queries.py            # Three query functions for RAG layer
│
├── docs/
│   ├── data_dictionary.md    # Every source field documented
│   └── schema.md             # Target DB schema (formal DDL + rationale)
│
└── scripts/
    ├── fetch_sample_data.py  # Download from Argovis API
    └── inspect_data.py       # Print field stats from raw files
```

---

## Running the Pipeline

### 1 — Start PostgreSQL

```bash
docker compose up -d
# Verify it's healthy:
docker compose ps
```

Expected output:
```
NAME            STATUS
floatchat_db    running (healthy)
```

### 2 — Fetch Sample Data

```bash
python scripts/fetch_sample_data.py --days 7 --start 2023-01-01
```

Downloads ~50–300 Indian Ocean profiles per day.  
Files land in `data/raw/argovis_indian_ocean_YYYY-MM-DD.json`.

Optional: set `ARGOVIS_TOKEN=your_token` in `.env` if you register at argovis.colorado.edu.

### 3 — Inspect Data (optional)

```bash
python scripts/inspect_data.py
```

Prints variable names, units, lat/lon range, temperature/salinity/pressure statistics,
and a 5-level sample profile.

### 4 — Run the ETL

```bash
# Normal run (loads all rows including flagged outliers)
python -m backend.load_data

# Drop physically implausible rows (strict mode)
python -m backend.load_data --drop-flagged

# Dry run — parse + validate without touching the DB
python -m backend.load_data --dry-run
```

### 5 — Re-runs

The ETL is **idempotent** — re-running it never duplicates rows.  
The DB uses `ON CONFLICT (float_id, cycle_number, pressure_dbar) DO NOTHING`.

---

## Running Queries

```python
from backend.queries import query_by_region, query_by_date_range, query_by_depth_band

# All observations in the Arabian Sea
rows = query_by_region(min_lat=5.0, max_lat=25.0, min_lon=55.0, max_lon=80.0)

# All observations in the first week of January 2023
rows = query_by_date_range("2023-01-01", "2023-01-07")

# All observations in the upper mixed layer (0–200 m)
rows = query_by_depth_band(0.0, 200.0)

# Each function returns a list of dicts — convert to DataFrame easily:
import pandas as pd
df = pd.DataFrame(rows)
print(df[["float_id", "lat", "lon", "depth_m", "temperature", "salinity", "timestamp"]].head())
```

Run the built-in demo:

```bash
python backend/queries.py
```

---

## For the AI/ML Teammate (RAG Layer)

### What's Ready

| Item | Location | Notes |
|---|---|---|
| PostgreSQL schema | `docs/schema.md` | Table `argo_profiles`, all columns defined |
| Query functions | `backend/queries.py` | Import and call directly |
| DB connection | `backend/db.py → get_connection()` | Uses `.env` credentials |

### Environment Variables You Need

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=floatchat
POSTGRES_PASSWORD=floatchat_dev
POSTGRES_DB=argo
```

### Query Function Signatures

```python
# Returns List[dict] — keys: id, float_id, cycle_number, lat, lon, timestamp,
#                            pressure_dbar, depth_m, temperature, salinity,
#                            basin, profile_direction, data_mode

query_by_region(min_lat, max_lat, min_lon, max_lon) → List[dict]
query_by_date_range(start_date: str, end_date: str) → List[dict]   # ISO-8601
query_by_depth_band(min_depth: float, max_depth: float) → List[dict]  # metres
```

All functions hard-cap at **10,000 rows** with a stderr warning — narrow your
parameters if you hit this limit.

### Useful Bounding Boxes (Indian Ocean)

| Region | min_lat | max_lat | min_lon | max_lon |
|---|---|---|---|---|
| Arabian Sea | 5 | 25 | 55 | 80 |
| Bay of Bengal | 5 | 22 | 80 | 100 |
| Full Indian Ocean | −10 | 25 | 40 | 105 |
| South Indian Ocean | −60 | −10 | 20 | 120 |

---

## Data Source Notes

**Primary source**: [Argovis](https://argovis.colorado.edu/) REST API  
- Endpoint: `GET https://argovis-api.colorado.edu/argo`  
- Floats sourced from INCOIS (Indian National Centre for Ocean Information Services)  
- Data modes: `R`=real-time, `A`=adjusted, `D`=delayed-mode (highest quality)

**Alternative (manual)**: INCOIS/GDAC FTP mirror  
- `ftp://ftp.ifremer.fr/ifremer/argo/dac/incois/`  
- See `scripts/fetch_sample_data.py` for NetCDF download instructions

---

## Schema Reference

See [`docs/schema.md`](docs/schema.md) for the full DDL and [`docs/data_dictionary.md`](docs/data_dictionary.md) for field-level source mapping.

Core table: **`argo_profiles`**

| Column | Type | Description |
|---|---|---|
| `float_id` | VARCHAR(20) | ARGO platform ID |
| `cycle_number` | INTEGER | Dive cycle number |
| `lat`, `lon` | DOUBLE PRECISION | Decimal degrees |
| `timestamp` | TIMESTAMPTZ | UTC observation time |
| `pressure_dbar` | REAL | Pressure in decibars |
| `depth_m` | REAL | Depth in metres (derived) |
| `temperature` | REAL | °C (NULL if bad/missing) |
| `salinity` | REAL | psu (NULL if bad/missing) |
