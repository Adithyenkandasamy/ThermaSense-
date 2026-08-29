"""Schemas for event analysis responses."""

from typing import Any

from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    event_id: int
    classification: str
    confidence: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=100)
    risk_level: str
    summary: str
    reasoning: list[str] = Field(default_factory=list)
    recommended_action: str
    evidence: dict[str, Any] = Field(default_factory=dict)
