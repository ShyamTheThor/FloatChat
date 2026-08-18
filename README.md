 # FloatChat — Oceanographic Intelligence Platform

> **AI-Powered Conversational Interface & Analytics Engine for ARGO Ocean Float Data**  
> *Ministry of Earth Sciences | Smart India Hackathon (SIH)*

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Key Architectural Highlights](#key-architectural-highlights)
3. [End-to-End System Architecture](#end-to-end-system-architecture)
4. [Technology Stack](#technology-stack)
5. [ARGO Data Pipeline & Validation](#argo-data-pipeline--validation)
6. [Scientific Depth Calibration](#scientific-depth-calibration)
7. [AI Query Intent Planner & RAG](#ai-query-intent-planner--rag)
8. [Database Schema & Idempotent Upsert](#database-schema--idempotent-upsert)
9. [API Reference](#api-reference)
10. [Quick Start & Setup](#quick-start--setup)
11. [Testing & Quality Gate](#testing--quality-gate)
12. [Security Guidelines](#security-guidelines)

---

## System Overview

FloatChat is a scientifically defensible oceanographic intelligence platform designed to convert natural language queries into validated, deterministic SQL queries over multi-dimensional ARGO ocean float data.

Instead of allowing Large Language Models (LLMs) to directly emit or execute arbitrary raw SQL commands, FloatChat uses a strict multi-layer execution pipeline:

```
[User Natural Language Query]
             │
             ▼
[ChromaDB Vector Retrieval (Domain Knowledge Metadata)]
             │
             ▼
[Groq LLM + Pydantic QueryIntent Schema Parser]
             │
             ▼
[Dataset Bounds & Business Rule Validation]
             │
             ▼
[Deterministic Parameterized SQL Compiler]
             │
             ▼
[PostgreSQL Database (argo_profiles)]
             │
             ▼
[Server-Side Analytics Engine (Numpy Summary Metrics)]
             │
             ▼
[Modern Oceanographic Intelligence Dashboard (React + Leaflet + Plotly)]
```

---

## Key Architectural Highlights

- **Deterministic Data Retrieval**: ARGO float measurements (temperature, salinity, pressure, depth) are fetched strictly from PostgreSQL via parameterized SQL queries compiled from validated Pydantic intent objects.
- **Pydantic Intent Validation**: Ensures latitude (-90° to 90°), longitude (-180° to 180°), depth bands, and parameters are range-checked before query compilation.
- **Dataset Coverage Awareness**: Dynamic `/dataset/metadata` endpoint checks PostgreSQL bounds so queries never rely on fragile relative dates ("last 7 days from today") for historical datasets.
- **Scientific Defensibility**: Pressure (`pressure_dbar`) is preserved as the primary sensor measurement, while vertical depth (`depth_m`) is derived using the Leroy & Parthiot (1998) hydrostatic model.
- **Server-Side Statistical Analytics**: Computes observation counts, float counts, mean/min/max metrics, and temporal bounds server-side for immediate display on KPI dashboard cards.
- **Interactive Visualization Suite**:
  - **Leaflet Map**: Marker deduplication by float profile, parameter-based color gradients, and hover popups.
  - **Plotly Depth Profiles**: Dual-axis reversed depth plots for temperature & salinity.
  - **Plotly Time Series**: Aggregated upper-layer (0–200m) thermal and salinity trends over time.
  - **Plotly T-S Diagrams**: Temperature vs. Salinity scatter plots with depth color-bar encoding.

---

## Technology Stack

- **Backend**: FastAPI (Python 3.11+), Uvicorn, Pydantic v2, Psycopg2
- **AI / RAG**: Groq (OpenAI-compatible client), ChromaDB (Persistent vector store)
- **Database**: PostgreSQL 15 (Docker Compose containerized)
- **Frontend**: React 19, Vite, React-Leaflet, React-Plotly.js, Lucide Icons
- **Testing**: Pytest, TestClient, Httpx

---

## Scientific Depth Calibration & Units

- **Primary Measurement**: Pressure ($p$, in decibars / `dbar`), measured directly by CTD sensors on ARGO profiling floats.
- **Derived Depth**: Vertical depth ($z$, in metres / `m`, positive downward) is estimated using the 2nd-order Leroy & Parthiot (1998) hydrostatic model:

$$\text{depth\_m} \approx p \times 0.9927 \times \left(1.0 + 5.25 \times 10^{-3} \sin^2\phi\right)$$

- **Uncertainty**: The hydrostatic approximation provides an accuracy of approximately $\pm 0.5\%$ across standard ocean depth columns (0–7000 m). Raw `pressure_dbar` is always retained in the database alongside derived `depth_m` to preserve data lineage.
- **Salinity**: Practical Salinity Scale 1978 (PSS-78), dimensionless, reported using standard oceanographic `psu` notation.
- **Temperature**: In-situ seawater temperature reported in degrees Celsius (`°C`, ITS-90 standard).

---

## Database Schema & Idempotent Upsert

Table: `argo_profiles`

```sql
CREATE TABLE IF NOT EXISTS argo_profiles (
    id                BIGSERIAL PRIMARY KEY,
    float_id          VARCHAR(20) NOT NULL,
    cycle_number      INTEGER,
    lat               DOUBLE PRECISION NOT NULL CONSTRAINT chk_lat CHECK (lat BETWEEN -90.0 AND 90.0),
    lon               DOUBLE PRECISION NOT NULL CONSTRAINT chk_lon CHECK (lon BETWEEN -180.0 AND 180.0),
    timestamp         TIMESTAMPTZ NOT NULL,
    pressure_dbar     REAL CONSTRAINT chk_pressure CHECK (pressure_dbar IS NULL OR pressure_dbar >= 0.0),
    depth_m           REAL CONSTRAINT chk_depth CHECK (depth_m IS NULL OR depth_m >= 0.0),
    temperature       REAL CONSTRAINT chk_temp CHECK (temperature IS NULL OR (temperature >= -2.5 AND temperature <= 40.0)),
    salinity          REAL CONSTRAINT chk_sal CHECK (salinity IS NULL OR (salinity >= 0.0 AND salinity <= 45.0)),
    basin             INTEGER,
    profile_direction CHAR(1),
    data_mode         CHAR(1),
    source_url        TEXT
);

-- Idempotent NULL-safe unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_profile_level 
    ON argo_profiles (float_id, COALESCE(cycle_number, -1), COALESCE(pressure_dbar, -1.0));
```

---

## API Reference

### 1. `GET /health`
Returns system status.
```json
{
  "status": "ok",
  "service": "FloatChat API"
}
```

### 2. `GET /dataset/metadata`
Returns spatial, temporal, and count metadata from PostgreSQL.
```json
{
  "status": "online",
  "earliest_date": "2023-01-01",
  "latest_date": "2023-01-07",
  "total_observations": 1284,
  "total_floats": 23,
  "total_profiles": 48
}
```

### 3. `POST /chat`
Accepts natural language query and returns text summary, visualization data payload, query intent specs, and analytics metrics.

Request:
```json
{
  "message": "Show me salinity in the Arabian Sea"
}
```

---

## Offline Deterministic Fallback & DEMO MODE

FloatChat includes an **offline deterministic semantic planner** in `backend/planner.py`:
- **Offline / Presentation Mode**: Set `DEMO_MODE=true` in `.env` to execute queries with deterministic domain parsing and structured summary generation locally without external LLM API calls.
- **Live Mode**: Calls the Groq LLM API (`openai/gpt-oss-120b`), automatically falling back to the deterministic planner if an API key expires, encounters rate limits, or network connectivity is interrupted.
- **Database Safety**: Both live and demo modes compile into identical parameterized SQL queries against PostgreSQL.

---

## Quick Start & Setup

### 1. Environment Configuration
Copy environment configuration template:
```bash
cp .env.example .env
```
Ensure `.env` contains:
```ini
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=floatchat
POSTGRES_PASSWORD=floatchat_dev
POSTGRES_DB=argo

FRONTEND_URL=http://localhost:5173
VITE_API_BASE_URL=http://localhost:8000
GROQ_API_KEY=your_groq_api_key_here
DEMO_MODE=false
```

### 2. Start PostgreSQL Database
```bash
docker compose up -d
```

### 3. Install Python Dependencies & Run ETL
```bash
python3 -m pip install -e .
python3 -m backend.load_data
```

### 4. Start FastAPI Backend
```bash
python3 backend/api.py
```

### 5. Start React Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Testing & Quality Gate

Run automated Pytest test suite:
```bash
python3 -m pytest tests/ -v
```

Run domain query benchmark (40 curated oceanographic test questions):
```bash
python3 scripts/eval_planner.py
```

Run frontend linting and build validation:
```bash
cd frontend
npm run lint
npm run build
```

---

## Security Guidelines

- Never commit real secrets or `.env` files to git repositories.
- Keep `GROQ_API_KEY` protected in environment variables.
- Production deployment enforces explicit origin CORS verification (`FRONTEND_URL`).
- Server logs record error tracebacks internally while returning the generic user-friendly messages to client applications.


