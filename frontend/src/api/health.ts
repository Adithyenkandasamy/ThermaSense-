import { apiGet } from "./client";

export type HealthResponse = {
  status: "ok" | "degraded";
  timestamp: string;
  service: string;
  version: string;
  checks: {
    database: "ok" | "error";
    postgis_version: string | null;
    database_error: string | null;
  };
};

export function getHealth(signal?: AbortSignal) {
  return apiGet<HealthResponse>("/health", signal);
}
