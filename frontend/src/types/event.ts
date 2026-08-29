export type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "EXTREME";

export type ThermalEventSummary = {
  id: number;
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
};
