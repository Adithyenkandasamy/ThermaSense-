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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Fetch thermal hotspot observations from the backend.
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

  const response = await fetch(url);

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(errorBody.detail || "Failed to fetch hotspots");
  }

  return response.json();
}

/**
 * Fetch weather context for a location (future use).
 */
export async function fetchWeather(
  latitude: number,
  longitude: number,
  date: string
): Promise<unknown> {
  const searchParams = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    date,
  });

  const url = `${API_BASE}/api/context/weather?${searchParams.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error("Failed to fetch weather data");
  }

  return response.json();
}

/**
 * Health check — confirm backend is reachable.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch {
    return false;
  }
}
