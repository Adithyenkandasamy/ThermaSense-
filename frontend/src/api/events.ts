import { apiGet } from "./client";
import type { ThermalEventSummary } from "../types/event";

export function listLatestEvents(signal?: AbortSignal) {
  return apiGet<ThermalEventSummary[]>("/api/v1/events/latest", signal);
}
