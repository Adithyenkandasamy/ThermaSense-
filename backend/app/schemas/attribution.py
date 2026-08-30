"""
Pydantic schemas for the Thermal Anomaly Attribution Engine.

Supports transparent rule-based scoring across:
  - vegetation_fire
  - agricultural_burning
  - industrial_heat
  - gas_flare
  - volcanic_activity
  - unknown
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

CauseType = Literal[
    "vegetation_fire",
    "agricultural_burning",
    "industrial_heat",
    "gas_flare",
    "volcanic_activity",
    "unknown",
]

EvidenceImpact = Literal["supports", "contradicts", "neutral"]
EvidenceSource = Literal["satellite", "weather", "geospatial"]


class EvidenceItem(BaseModel):
    """A single piece of supporting or contradictory evidence."""

    factor: str = Field(..., description="The parameter/feature evaluated")
    value: str = Field(..., description="The observed value or context metric")
    impact: EvidenceImpact = Field(..., description="Direction of impact ('supports', 'contradicts', 'neutral')")
    source: EvidenceSource = Field(..., description="Evidence data source ('satellite', 'weather', 'geospatial')")
    supports_cause: Optional[CauseType] = Field(None, description="The specific cause supported, if applicable")


class CauseScore(BaseModel):
    """Score and confidence breakdown for an individual cause hypothesis."""

    cause: CauseType = Field(..., description="The cause hypothesis")
    score: float = Field(..., description="Raw point score from rules")
    normalized_score: float = Field(..., description="Normalized confidence probability (0.0 - 1.0)")


class AttributionResult(BaseModel):
    """Complete, structured output from the Attribution Engine."""

    primary_cause: CauseType = Field(..., description="Determined most likely cause")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence level (0.0 - 1.0)")
    possible_causes: list[CauseScore] = Field(
        default_factory=list,
        description="Preserved individual cause scores for frontend visualization / multi-model fusion",
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Transparent list of all factors, values, impacts, and sources",
    )
    reasoning_summary: str = Field(..., description="Human-readable synthesis explaining the classification")
    entity_type: Literal["event", "observation"] = Field("event", description="Type of entity analyzed")
    entity_id: str = Field(..., description="UUID of analyzed ThermalEvent or ThermalObservation")
    classified_at: datetime = Field(..., description="Timestamp when analysis was generated")


# Backward compatibility alias
AttributionResponse = AttributionResult
