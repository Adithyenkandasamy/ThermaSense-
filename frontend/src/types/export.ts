/**
 * Type definitions for GIS Export and Operational Thermal Alerts (Module 6).
 */

export type AlertSeverity = "CRITICAL" | "WARNING" | "INFO";

export interface ThermalAlert {
  alert_id: string;
  event_id?: string | null;
  severity: AlertSeverity;
  title: string;
  message: string;
  latitude: number;
  longitude: number;
  frp?: number | null;
  triggered_at: string;
  rule_name: string;
}

export interface AlertListResponse {
  total: number;
  alerts: ThermalAlert[];
}
