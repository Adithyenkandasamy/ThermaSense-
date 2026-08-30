/**
 * Type definitions for Thermal Events (Module 4 & 5).
 */

export interface EventObservationSummary {
  id: string;
  latitude: number;
  longitude: number;
  acquisition_datetime: string;
  satellite: string;
  instrument: string;
  brightness?: number | null;
  frp?: number | null;
  confidence?: string | null;
}

export interface ThermalEvent {
  id: string;
  status: "active" | "inactive";
  centroid_latitude: number;
  centroid_longitude: number;
  started_at: string;
  ended_at?: string | null;
  last_detected_at?: string | null;
  total_frp?: number | null;
  max_frp?: number | null;
  max_confidence?: string | null;
  observation_count: number;
  description?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  observations?: EventObservationSummary[];
}

export interface EventListResponse {
  total: number;
  limit: number;
  offset: number;
  events: ThermalEvent[];
}
