/**
 * Type definitions for continuous monitoring and ingestion logs.
 */

export interface MonitoringStatus {
  monitoring_enabled: boolean;
  scheduler_running: boolean;
  poll_interval_minutes: number;
  monitoring_area: string;
  sources: string[];
  last_successful_ingestion: string | null;
  next_scheduled_run: string | null;
  last_ingestion_status: string | null;
}

export interface IngestionLog {
  id: string;
  source: string;
  area: string;
  day_range: number;
  requested_at: string;
  completed_at: string | null;
  status: "pending" | "success" | "partial" | "error" | string;
  records_fetched: number;
  records_validated: number;
  records_stored: number;
  duplicates_skipped: number;
  invalid_records: number;
  error_message: string | null;
}

export interface MonitoringLogsResponse {
  total: number;
  limit: number;
  offset: number;
  logs: IngestionLog[];
}

export interface MonitoringRunResponse {
  status: string;
  timestamp?: string;
  results: Array<Record<string, unknown>>;
}
