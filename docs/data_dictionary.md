# Data Dictionary — ARGO Ocean Float Data

> Source: Argovis REST API (https://argovis-api.colorado.edu/argo)  
> Verified against live API response on 2026-08-17  
> Reference floats: INCOIS-managed floats 2902275, 2902277, 2902837 (Indian Ocean)

---

## Source Format

Argovis returns a **JSON array** of profile objects.  
Each profile represents one float surfacing event (one cycle).  
Each profile contains **N depth levels** stored as parallel arrays inside `data[]`.

---

## Profile-Level Fields

| Field | Type | Example | Meaning | Maps To (clean schema) |
|---|---|---|---|---|
| `_id` | string | `"2902275_239"` | `{platform_id}_{cycle_number}` — unique per profile | `float_id` + `cycle_number` |
| `geolocation` | GeoJSON Point | `{"type":"Point","coordinates":[70.67,16.45]}` | Surface position when float reported | `lon`, `lat` |
| `geolocation.coordinates[0]` | float | `70.674057` | **Longitude** (East positive) — note GeoJSON order lon,lat | `lon` |
| `geolocation.coordinates[1]` | float | `16.453152` | **Latitude** (North positive) | `lat` |
| `timestamp` | ISO-8601 string | `"2023-01-01T19:12:04.000Z"` | UTC time of the profile observation | `timestamp` |
| `cycle_number` | integer | `239` | Sequential dive number for this float | `cycle_number` |
| `basin` | integer | `3` | Ocean basin code (3 = Indian Ocean) | `basin` *(optional)* |
| `profile_direction` | string | `"A"` | `"A"` = ascending, `"D"` = descending | `profile_direction` *(optional)* |
| `vertical_sampling_scheme` | string | `"Primary sampling: averaged []"` | How depth levels were collected | not stored |
| `date_updated_argovis` | ISO-8601 | `"2026-07-10T11:13:14.594Z"` | When Argovis last updated this record | not stored |
| `source` | array | `[{"source":["argo_core"],"url":"ftp://..."}]` | Origin NetCDF file URL(s) per data type | `source_url` (first entry) |
| `geolocation_argoqc` | integer | `1` | QC flag for position (1 = good) | not stored (always filter ≥1) |
| `timestamp_argoqc` | integer | `1` | QC flag for time (1 = good) | not stored |
| `metadata` | array | `["2902275_m0"]` | Reference to float metadata record | not stored |

---

## Level-Level Fields (`data[]` Arrays)

Each profile's `data` key is a 2D array: `data[variable_index][level_index]`.  
The mapping of index → variable is described in `data_info[0]`.

### `data_info` Structure

```json
"data_info": [
  ["temperature", "salinity", "pressure"],   // [0] variable names
  ["units", "data_keys_mode"],               // [1] column labels
  [                                          // [2] per-variable metadata
    ["degree_Celsius", "D"],                 //     temperature unit + mode
    ["psu",            "D"],                 //     salinity unit + mode
    ["decibar",        "D"]                  //     pressure unit + mode
  ]
]
```

**Data modes**: `R` = real-time, `A` = adjusted real-time, `D` = delayed-mode (highest quality)

### Measured Variables

| Variable | `data` Index | Unit | Typical Range | Meaning | Maps To |
|---|---|---|---|---|---|
| `temperature` | `0` | `degree_Celsius` | −2 … 35 °C | In-situ seawater temperature | `temperature` |
| `salinity` | `1` | `psu` | 0 … 42 psu | Practical Salinity Unit (PSS-78) | `salinity` |
| `pressure` | `2` | `decibar` | 0 … 7000 dbar | Sea pressure (≈ depth in m × 1.0) | `pressure_dbar` |

### Null Handling

Raw values of `null` (JSON null → Python `None`) appear in real data — they represent:
- Levels where sensor data was flagged as bad
- Gaps in the measurement record
- End-of-profile padding in fixed-length arrays

**Pipeline decision**: NULL values are stored as `NULL` in PostgreSQL (not dropped).  
This preserves data lineage. The `validate.py` module counts and reports them.

---

## Derived Fields (computed by `backend/parser.py`)

| Field | Formula | Unit | Notes |
|---|---|---|---|
| `depth_m` | `pressure_dbar × 0.9927 × (1 + 5.25×10⁻³ × sin²(lat))` | metres | Simplified Leroy/UNESCO formula. Accurate to ±0.5% for 0–2000 m. |

---

## ARGO NetCDF Reference (for future INCOIS direct integration)

If the team later integrates NetCDF files from INCOIS/GDAC directly, the field mapping is:

| NetCDF Variable | Meaning | Argovis Equivalent |
|---|---|---|
| `JULD` | Julian Day (days since 1950-01-01) | `timestamp` |
| `LATITUDE` | Profile latitude | `geolocation.coordinates[1]` |
| `LONGITUDE` | Profile longitude | `geolocation.coordinates[0]` |
| `PRES` | Pressure (dbar) | `data[2]` |
| `TEMP` | Temperature (°C) | `data[0]` |
| `PSAL` | Salinity (psu) | `data[1]` |
| `TEMP_QC` | Temperature QC flag | not in Argovis per-level |
| `PSAL_QC` | Salinity QC flag | not in Argovis per-level |
| `TEMP_ADJUSTED` | Delayed-mode calibrated temperature | Argovis serves this when mode=D |
| `DATA_MODE` | R/A/D per profile | `data_info[2][i][1]` |
| `PLATFORM_NUMBER` | Float ID | first part of `_id` |
| `CYCLE_NUMBER` | Dive cycle | second part of `_id` |

---

## Basin Codes (Argovis)

| Code | Basin |
|---|---|
| `3` | Indian Ocean |
| `56` | Bay of Bengal |
| `1` | Atlantic Ocean |
| `2` | Pacific Ocean |

---

*Generated 2026-08-17. Update this file if new variables appear after `inspect_data.py` is run on expanded datasets.*
