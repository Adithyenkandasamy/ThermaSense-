/**
 * Type definitions for Module 3 Geospatial & Weather Context.
 */

export interface NearbyFeature {
  feature_type: string;
  name: string | null;
  distance_m: number | null;
  osm_id: number | null;
  osm_type: string | null;
  tags: Record<string, string>;
}

export interface GeospatialContextResponse {
  latitude: number;
  longitude: number;
  radius_m: number;
  industrial: NearbyFeature[];
  forests: NearbyFeature[];
  croplands: NearbyFeature[];
  roads: NearbyFeature[];
  buildings: NearbyFeature[];
  source: string;
}

export interface WeatherContextResponse {
  latitude: number;
  longitude: number;
  date: string;
  temperature_max: number | null;
  temperature_min: number | null;
  apparent_temperature_max: number | null;
  precipitation_sum: number | null;
  wind_speed_max: number | null;
  wind_direction_dominant: number | null;
  relative_humidity_mean: number | null;
  weather_code: number | null;
  source: string;
}
