/**
 * Type definitions for thermal hotspot observations.
 */

/** Satellite source identifiers */
export type SatelliteSource = "NOAA-20" | "NOAA-21";

/** A single thermal hotspot observation from FIRMS */
export interface Hotspot {
  id: string;
  latitude: number;
  longitude: number;
  acquisition_datetime: string;
  satellite: string;
  instrument: string;
  brightness: number | null;
  bright_ti4: number | null;
  bright_ti5: number | null;
  frp: number | null;
  confidence: string | null;
  daynight: string | null;
  source: string;
}

/** Response from GET /api/hotspots */
export interface HotspotListResponse {
  total: number;
  satellite_source: string;
  day_range: number;
  area: string;
  observations: Hotspot[];
}

/** Fetch parameters for hotspot queries */
export interface HotspotFetchParams {
  satellite: SatelliteSource;
  days: number;
  bbox?: string;
}

/** API error shape */
export interface ApiError {
  detail: string;
}
