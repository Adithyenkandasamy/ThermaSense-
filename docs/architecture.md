# ThermaSense Architecture

## System Overview

ThermaSense is a modular geospatial intelligence platform that collects
satellite thermal anomaly data and helps users investigate what detected
thermal hotspots may represent.

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                                                                 │
│  Next.js Frontend                                               │
│  ├── Interactive Leaflet Map (dark-themed, full-page)           │
│  ├── Satellite Source Filters (NOAA-20, NOAA-21)                │
│  ├── Date Range Selector (1–5 days)                             │
│  ├── Hotspot Markers (color-coded by confidence)                │
│  └── Observation Detail Panel                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                          REST API                               │
│                                                                 │
│  FastAPI Backend                                                │
│  ├── GET  /health                                               │
│  ├── GET  /api/hotspots?satellite=NOAA-20&days=1&bbox=...       │
│  ├── GET  /api/hotspots/{id}                                    │
│  ├── POST /api/ingestion/firms                                  │
│  └── GET  /api/context/weather?lat=...&lon=...&date=...         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                        SERVICE LAYER                            │
│                                                                 │
│  firms_service.py      ── NASA FIRMS Area API integration       │
│  weather_service.py    ── Open-Meteo weather context            │
│  geospatial_service.py ── OSM / Overpass context (placeholder)  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                     EXTERNAL DATA SOURCES                       │
│                                                                 │
│  NASA FIRMS API ──── VIIRS_NOAA20_NRT / VIIRS_NOAA21_NRT       │
│  Open-Meteo API ──── Weather conditions (no key required)       │
│  Overpass API ─────── OSM geographic context (future)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
NASA FIRMS
     ↓
FastAPI Backend
     ↓
FIRMS Service (firms_service.py)
     ↓
CSV Parsing & Validation
     ↓
Structured JSON (HotspotResponse)
     ↓
REST API Response
     ↓
Next.js Frontend (fetch via services/api.ts)
     ↓
Interactive Leaflet Map
```

## Core Architectural Distinction

The system separates two concepts:

- **Satellite Observation**: A raw detection from a satellite sensor
  indicating heat at a specific location and time. This is what the
  MVP works with.

- **Real-World Event**: A classified occurrence (wildfire, industrial
  heat, agricultural burning, etc.) derived from one or more
  observations combined with contextual intelligence. This is a
  future phase.

Multiple observations from different satellites or times must NOT
automatically be considered duplicates. They are independent evidence.

## Module Architecture

Each service is isolated in its own file and can be extended
independently:

| Service                  | File                      | Status       |
| ------------------------ | ------------------------- | ------------ |
| FIRMS Integration        | `firms_service.py`        | Implemented  |
| Database Persistence     | `observation_service.py`  | Implemented  |
| Deduplication Engine     | `observation_normalizer.py`| Implemented |
| Ingestion Logging        | `ingestion_repository.py` | Implemented  |
| Monitoring Scheduler     | `firms_scheduler.py`      | Implemented  |
| Weather Context          | `weather_service.py`      | Implemented  |
| Geospatial Context       | `geospatial_service.py`   | Implemented  |
| Event Clustering         | *(future)*                | Not started  |
| Attribution Engine       | *(future)*                | Not started  |
| Historical Analysis      | *(future)*                | Not started  |


## Future Extensions

The following modules can be added without modifying existing services:

1. **Event clustering** — Group nearby observations into events
2. **ML attribution** — Classify event causes using contextual features
3. **Historical analysis** — Track patterns over time
4. **Explainability** — Provide evidence-based reasoning for classifications

