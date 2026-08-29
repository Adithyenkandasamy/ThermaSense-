import { apiGet } from "./client";

export type DashboardSummary = {
  active_events: number;
  high_risk: number;
  extreme_risk: number;
  api_status: string;
  database_status: string;
  demo_mode: boolean;
};

export function getDashboardSummary(signal?: AbortSignal) {
  return apiGet<DashboardSummary>("/api/v1/dashboard/summary", signal);
}
