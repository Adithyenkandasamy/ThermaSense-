/**
 * API client for the ThermaSense backend.
 *
 * All calls to the backend go through this module so
 * the base URL is configured in one place.
 */

import type {
  HotspotFetchParams,
  HotspotListResponse,
} from "@/types/hotspot";
import type {
  MonitoringLogsResponse,
  MonitoringRunResponse,
  MonitoringStatus,
} from "@/types/monitoring";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://127.0.0.1:8000"
    : "http://127.0.0.1:8000");
const DEFAULT_TIMEOUT_MS = 8000;

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Request timed out. Please check backend connection.");
    }
    if (err instanceof Error && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError"))) {
      throw new Error("Cannot connect to backend service. Ensure backend is running on port 8000.");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch stored observations directly from the database (Module 2).
 */
export async function fetchStoredObservations(params?: {
  satellite?: string;
  source?: string;
  limit?: number;
  offset?: number;
}): Promise<HotspotListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.satellite) searchParams.set("satellite", params.satellite);
  if (params?.source) searchParams.set("source", params.source);
  searchParams.set("limit", String(params?.limit || 300));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const url = `${API_BASE}/api/observations?${searchParams.toString()}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch stored observations: HTTP ${response.status}`);
  }

  const data = await response.json();
  return {
    total: data.total,
    satellite_source: params?.satellite || "ALL",
    day_range: 7,
    area: "Stored Observations",
    observations: data.observations,
  };
}

/**
 * Fetch thermal hotspot observations from the backend.
 * Seamlessly queries live FIRMS with automatic fallback to stored database observations.
 */
export async function fetchHotspots(
  params: HotspotFetchParams
): Promise<HotspotListResponse> {
  const searchParams = new URLSearchParams({
    satellite: params.satellite,
    days: String(params.days),
  });

  if (params.bbox) {
    searchParams.set("bbox", params.bbox);
  }

  const url = `${API_BASE}/api/hotspots?${searchParams.toString()}`;

  try {
    const response = await fetchWithTimeout(url, {}, 5000);
    if (response.ok) {
      const data = await response.json();
      if (data.observations && data.observations.length > 0) {
        return data;
      }
    }
  } catch {
    // Fallback to stored database observations if live fetch is unavailable or times out
  }

  // Retrieve stored database observations
  return await fetchStoredObservations({
    satellite: params.satellite,
    limit: 300,
  });
}


/**
 * Fetch monitoring system status and scheduler state (Module 2).
 */
export async function fetchMonitoringStatus(): Promise<MonitoringStatus> {
  const response = await fetchWithTimeout(`${API_BASE}/api/monitoring/status`);
  if (!response.ok) {
    throw new Error("Failed to fetch monitoring status");
  }
  return response.json();
}

/**
 * Fetch ingestion history logs (Module 2).
 */
export async function fetchMonitoringLogs(
  params?: { source?: string; status?: string; limit?: number; offset?: number }
): Promise<MonitoringLogsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.source) searchParams.set("source", params.source);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  const url = `${API_BASE}/api/monitoring/logs${qs ? `?${qs}` : ""}`;
  const response = await fetchWithTimeout(url);
  if (!response.ok) {
    throw new Error("Failed to fetch monitoring logs");
  }
  return response.json();
}

/**
 * Trigger manual monitoring ingestion cycle (Module 2).
 */
export async function triggerMonitoringRun(): Promise<MonitoringRunResponse> {
  const response = await fetchWithTimeout(`${API_BASE}/api/monitoring/run`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to trigger monitoring run");
  }
  return response.json();
}

import type {
  GeospatialContextResponse,
  WeatherContextResponse,
} from "@/types/context";

/**
 * Fetch weather context for a location (Module 3).
 */
export async function fetchWeather(
  latitude: number,
  longitude: number,
  date: string
): Promise<WeatherContextResponse> {
  const searchParams = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    date,
  });

  const url = `${API_BASE}/api/context/weather?${searchParams.toString()}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) {
    throw new Error("Failed to fetch weather data");
  }

  return response.json();
}

/**
 * Fetch geospatial land use and feature context from OpenStreetMap (Module 3).
 */
export async function fetchGeospatialContext(
  latitude: number,
  longitude: number,
  radius_m = 2000
): Promise<GeospatialContextResponse> {
  const searchParams = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    radius_m: String(radius_m),
  });

  const url = `${API_BASE}/api/context/geospatial?${searchParams.toString()}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) {
    throw new Error("Failed to fetch geospatial context");
  }

  return response.json();
}



import type { AttributionResult } from "@/types/attribution";

/**
 * Fetch automated cause attribution for an observation (Module 5).
 */
export async function fetchAttributionForObservation(
  observationId: string
): Promise<AttributionResult> {
  const url = `${API_BASE}/api/attribution/observation/${encodeURIComponent(observationId)}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(errBody.detail || "Failed to fetch observation attribution");
  }

  return response.json();
}

/**
 * Fetch automated cause attribution for a clustered event (Module 5).
 */
export async function fetchAttributionForEvent(
  eventId: string
): Promise<AttributionResult> {
  const url = `${API_BASE}/api/attribution/event/${encodeURIComponent(eventId)}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(errBody.detail || "Failed to fetch event attribution");
  }

  return response.json();
}

/**
 * Health check — confirm backend is reachable.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(`${API_BASE}/health`, {}, 3000);
    return response.ok;
  } catch {
    return false;
  }
}



