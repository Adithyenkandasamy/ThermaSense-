// ── Core domain types (mirror backend schemas) ──────────────────────────────

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'EXTREME';

export interface ThermalEventSummary {
  id: number;
  source: string;
  latitude: number;
  longitude: number;
  acq_date: string;
  acq_time: string;
  frp: number | null;
  brightness: number | null;
  confidence: string | null;
  satellite: string | null;
  risk_level: RiskLevel;
  risk_score: number;
  ai_summary: string | null;
}

export interface ThermalEventDetail extends ThermalEventSummary {
  external_id: string | null;
  instrument: string | null;
  daynight: string | null;
  scan: number | null;
  track: number | null;
  ai_generated: boolean;
  created_at: string;
  updated_at: string;
}

export interface Facility {
  id: number;
  name: string;
  type: string;
  distance_km: number;
  latitude: number;
  longitude: number;
  source: string;
}

export interface EventContext {
  event_id: number;
  location: { latitude: number; longitude: number };
  nearby_facilities: Facility[];
  nearest_facility: Facility | null;
  nearest_facility_km: number | null;
  land_cover: string;
  radius_km: number;
}

export interface EventHistory {
  event_id: number;
  radius_km: number;
  detections_7d: number;
  detections_30d: number;
  detections_90d: number;
  active_days: number;
  average_frp: number | null;
  maximum_frp: number | null;
  historical_baseline: number | null;
  current_frp: number;
  anomaly_ratio: number | null;
  persistence_score: number;
  has_history: boolean;
}

export interface EventAnalysis {
  id: number;
  classification: string;
  confidence: number;
  risk_score: number;
  risk_level: RiskLevel;
  persistence_score: number;
  anomaly_score: number;
  industrial_context_score: number;
  summary: string;
  reasoning: string;
  recommended_action: string;
  engine_version: string;
  created_at: string;
  updated_at: string;
  ai_mode: string;
}

export interface FullAnalysis {
  event: ThermalEventDetail;
  context: EventContext;
  history: EventHistory;
  analysis: EventAnalysis;
}

export interface Stats {
  total_events: number;
  by_risk_level: Record<string, number>;
  last_ingestion: string | null;
  events_last_24h: number;
  extreme_count: number;
  high_count: number;
}

export interface Alert {
  event_id: number;
  risk_level: RiskLevel;
  risk_score: number;
  classification: string;
  latitude: number;
  longitude: number;
  frp: number | null;
  timestamp: string;
  summary: string;
  simulated: boolean;
  confidence: number | null;
}

// ── WebSocket message types ──────────────────────────────────────────────────

export interface WsConnected {
  type: 'CONNECTED';
  message: string;
  active_connections: number;
}

export interface WsEventAnalyzed {
  type: 'THERMAL_EVENT_ANALYZED';
  event_id: number;
  classification: string;
  risk_level: RiskLevel;
  risk_score: number;
  latitude: number;
  longitude: number;
  frp: number | null;
  scenario?: string;
  simulated?: boolean;
}

export interface WsThermalAlert {
  type: 'THERMAL_ALERT';
  event_id: number;
  risk_level: RiskLevel;
  risk_score: number;
  classification: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  summary: string;
  simulated: boolean;
}

export interface WsPong { type: 'PONG' }

export type WsMessage = WsConnected | WsEventAnalyzed | WsThermalAlert | WsPong;

// ── Simulation types ─────────────────────────────────────────────────────────

export type Scenario = 'industrial' | 'wildfire' | 'agricultural' | 'mining' | 'persistent' | 'extreme';

export interface SimulateRequest {
  scenario: Scenario;
  latitude?: number;
  longitude?: number;
  frp?: number;
  brightness?: number;
  confidence?: string;
}

export interface SimulateResponse {
  status: string;
  event_id: number;
  scenario: string;
  label: string;
  simulated: boolean;
  classification: string;
  risk_level: RiskLevel;
  risk_score: number;
  analysis_id: number;
  ai_mode: string;
  alert_broadcast: boolean;
  message: string;
}
