export type Analysis = {
  event_id: number;
  classification: string;
  confidence: number;
  risk_score: number;
  risk_level: string;
  summary: string;
  reasoning: string[];
  recommended_action: string;
};
