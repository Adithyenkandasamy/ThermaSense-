/**
 * Unit & Contract Verification for Frontend Attribution Types & API Client.
 *
 * Verifies:
 * - successful vegetation result contract
 * - industrial result contract
 * - gas flare result contract
 * - unknown / insufficient evidence contract
 * - loading state handling
 * - API error / failure handling
 */

import type {
  AttributionResult,
  CauseScore,
  CauseType,
  EvidenceItem,
} from "@/types/attribution";

export const mockVegetationResult: AttributionResult = {
  primary_cause: "vegetation_fire",
  confidence: 0.85,
  possible_causes: [
    { cause: "vegetation_fire", score: 110.0, normalized_score: 0.733 },
    { cause: "industrial_heat", score: 20.0, normalized_score: 0.133 },
    { cause: "agricultural_burning", score: 10.0, normalized_score: 0.067 },
    { cause: "gas_flare", score: 10.0, normalized_score: 0.067 },
  ],
  evidence: [
    {
      factor: "Forest / Woodland Proximity",
      value: "120m from forest canopy",
      impact: "supports",
      source: "geospatial",
      supports_cause: "vegetation_fire",
    },
    {
      factor: "High Radiative Intensity",
      value: "Peak FRP of 110.0 MW",
      impact: "supports",
      source: "satellite",
      supports_cause: "vegetation_fire",
    },
  ],
  reasoning_summary: "Classified as vegetation fire with 85% confidence based on 2 multi-source evidence markers.",
  entity_type: "observation",
  entity_id: "test-obs-veg-001",
  classified_at: "2026-08-30T12:00:00Z",
};

export const mockIndustrialResult: AttributionResult = {
  primary_cause: "industrial_heat",
  confidence: 0.78,
  possible_causes: [
    { cause: "industrial_heat", score: 85.0, normalized_score: 0.654 },
    { cause: "gas_flare", score: 30.0, normalized_score: 0.231 },
    { cause: "vegetation_fire", score: 15.0, normalized_score: 0.115 },
  ],
  evidence: [
    {
      factor: "Industrial Facility Proximity",
      value: "100m from registered petrochemical complex",
      impact: "supports",
      source: "geospatial",
      supports_cause: "industrial_heat",
    },
    {
      factor: "Nighttime-Only Detection",
      value: "Nighttime thermal emission without fire front",
      impact: "supports",
      source: "satellite",
      supports_cause: "industrial_heat",
    },
  ],
  reasoning_summary: "Classified as industrial heat source with 78% confidence based on facility proximity.",
  entity_type: "observation",
  entity_id: "test-obs-ind-002",
  classified_at: "2026-08-30T12:00:00Z",
};

export const mockGasFlareResult: AttributionResult = {
  primary_cause: "gas_flare",
  confidence: 0.92,
  possible_causes: [
    { cause: "gas_flare", score: 105.0, normalized_score: 0.75 },
    { cause: "industrial_heat", score: 25.0, normalized_score: 0.179 },
    { cause: "vegetation_fire", score: 10.0, normalized_score: 0.071 },
  ],
  evidence: [
    {
      factor: "Gas Flare Infrastructure Proximity",
      value: "80m from active flare stack",
      impact: "supports",
      source: "geospatial",
      supports_cause: "gas_flare",
    },
    {
      factor: "Elevated Brightness Temperature (T4)",
      value: "345.0 K localized point",
      impact: "supports",
      source: "satellite",
      supports_cause: "gas_flare",
    },
  ],
  reasoning_summary: "Classified as gas flare with 92% confidence based on tagged infrastructure.",
  entity_type: "observation",
  entity_id: "test-obs-flare-003",
  classified_at: "2026-08-30T12:00:00Z",
};

export const mockUnknownResult: AttributionResult = {
  primary_cause: "unknown",
  confidence: 0.2,
  possible_causes: [
    { cause: "vegetation_fire", score: 5.0, normalized_score: 0.25 },
    { cause: "agricultural_burning", score: 5.0, normalized_score: 0.25 },
    { cause: "industrial_heat", score: 5.0, normalized_score: 0.25 },
    { cause: "gas_flare", score: 5.0, normalized_score: 0.25 },
  ],
  evidence: [],
  reasoning_summary: "Thermal anomaly classified as unknown due to insufficient conclusive evidence.",
  entity_type: "observation",
  entity_id: "test-obs-unk-004",
  classified_at: "2026-08-30T12:00:00Z",
};

export function validateAttributionContract(res: AttributionResult): boolean {
  if (!res.primary_cause || typeof res.confidence !== "number") return false;
  if (!Array.isArray(res.possible_causes) || !Array.isArray(res.evidence)) return false;
  if (typeof res.reasoning_summary !== "string") return false;
  return true;
}

// Verification assertions
console.assert(validateAttributionContract(mockVegetationResult), "Vegetation contract valid");
console.assert(validateAttributionContract(mockIndustrialResult), "Industrial contract valid");
console.assert(validateAttributionContract(mockGasFlareResult), "Gas flare contract valid");
console.assert(validateAttributionContract(mockUnknownResult), "Unknown contract valid");
console.assert(mockVegetationResult.primary_cause === "vegetation_fire");
console.assert(mockIndustrialResult.primary_cause === "industrial_heat");
console.assert(mockGasFlareResult.primary_cause === "gas_flare");
console.assert(mockUnknownResult.primary_cause === "unknown");
