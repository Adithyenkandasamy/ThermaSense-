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
 
Hourly weather context is fetched from the [Open-Meteo API](https://open-meteo.com/) matching the exact observation acquisition timestamp.
No API key is required.
 
### Endpoint
 
```
GET /api/context/weather?latitude={lat}&longitude={lon}&acquisition_datetime={ISO8601_UTC}
```
 
### Data Returned
 
- Temperature (`temperature`, °C)
- Relative Humidity (`relative_humidity`, %)
- Wind Speed (`wind_speed`, km/h)
- Wind Direction (`wind_direction`, degrees)
- Precipitation (`precipitation`, mm)
- Weather Timestamp (`weather_timestamp`, hourly UTC bucket)
- Source (`open-meteo`)
 
### API Selection
 
- Observations within the last 92 days use the **Forecast API**
- Older observations use the historical **Archive API**
 
---
 
## OpenStreetMap / Overpass
 
### Overview
 
The `geospatial_service.py` provides real-time land use and infrastructure context around thermal observations using OpenStreetMap data via the Overpass API:
 
- **Industrial areas & facilities**: `landuse=industrial`, `man_made=flare`, `power=plant`
- **Forests & vegetation**: `landuse=forest`, `natural=wood`
- **Agricultural farmlands**: `landuse=farmland`, `landuse=orchard`, `landuse=farmyard`
- **Roads & transport corridors**: `highway=motorway|trunk|primary|secondary`
- **Buildings**: `building=*`
 
### Endpoint
 
```
GET /api/context/geospatial?latitude={lat}&longitude={lon}&radius_m=2000
```
 
### Overpass API Target
 
```
https://overpass-api.de/api/interpreter
```
 
Features are returned with Haversine distance in meters from the anomaly point and cached for 1 hour using coordinate rounding keys to prevent rate limiting.
