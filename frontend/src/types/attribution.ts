/**
 * TypeScript types for the Backend Thermal Anomaly Attribution Engine.
 */

export type CauseType =
  | "vegetation_fire"
  | "agricultural_burning"
  | "industrial_heat"
  | "gas_flare"
  | "volcanic_activity"
  | "unknown";

export type EvidenceImpact = "supports" | "contradicts" | "neutral";
export type EvidenceSource = "satellite" | "weather" | "geospatial";

export interface EvidenceItem {
  factor: string;
  value: string;
  impact: EvidenceImpact;
  source: EvidenceSource;
  supports_cause?: CauseType;
}

export interface CauseScore {
  cause: CauseType;
  score: number;
  normalized_score: number;
}

export interface AttributionResult {
  primary_cause: CauseType;
  confidence: number;
  possible_causes: CauseScore[];
  evidence: EvidenceItem[];
  reasoning_summary: string;
  entity_type?: "event" | "observation";
  entity_id?: string;
  classified_at?: string;
}
