# API Integration Guide

## NASA FIRMS

### Overview

ThermaSense fetches near real-time thermal anomaly data from the
[NASA FIRMS Area API](https://firms.modaps.eosdis.nasa.gov/api/area/).

### Authentication

A free MAP_KEY is required. Obtain one at:
https://firms.modaps.eosdis.nasa.gov/api/

Store it in the backend `.env` file:

```env
FIRMS_MAP_KEY=your_key_here
```

The key is NEVER exposed to the frontend. All FIRMS requests go
through the backend.

### API Format

```
GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{area}/{day_range}
```

### Supported Sources

| Satellite | FIRMS Source ID       |
| --------- | -------------------- |
| NOAA-20   | `VIIRS_NOAA20_NRT`   |
| NOAA-21   | `VIIRS_NOAA21_NRT`   |

### Area Parameter

- `world` — Global data (default)
- `xmin,ymin,xmax,ymax` — Custom bounding box in WGS84

### Day Range

1 to 5 days of historical data.

### Response Format

CSV with columns:
```
latitude, longitude, bright_ti4, bright_ti5, scan, track,
acq_date, acq_time, satellite, instrument, confidence,
version, frp, daynight
```

### Error Handling

The backend returns clear error messages when:
- `FIRMS_MAP_KEY` is not configured (400)
- FIRMS API returns an error (502)
- Network timeout (502)
- Invalid satellite name (400)

---

## Open-Meteo

### Overview

Weather context is fetched from the [Open-Meteo API](https://open-meteo.com/).
No API key is required.

### Endpoint

```
GET /api/context/weather?latitude={lat}&longitude={lon}&date={YYYY-MM-DD}
```

### Data Returned

- Temperature (max/min)
- Apparent temperature
- Precipitation
- Wind speed and direction
- Weather code (WMO)

### API Selection

- Dates within the last 7 days use the **Forecast API**
- Older dates use the **Archive API**

---

## OpenStreetMap / Overpass (Future)

### Planned Integration

The `geospatial_service.py` defines interfaces for querying
nearby geographic features:

- Industrial areas
- Buildings
- Roads
- Forests / vegetation
- General land use

### Overpass API

```
https://overpass-api.de/api/interpreter
```

This integration is not yet implemented. The service skeleton
is ready for Overpass query integration without changing any
other service modules.
