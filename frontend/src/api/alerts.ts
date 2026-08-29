import { apiGet } from "./client";
import type { ThermalEventSummary } from "../types/event";

export function listAlerts(signal?: AbortSignal) {
  return apiGet<ThermalEventSummary[]>("/api/v1/alerts", signal);
}
