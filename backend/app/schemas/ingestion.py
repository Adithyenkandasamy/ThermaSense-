"""
Pydantic schemas for ingestion API (Module 2).
"""

from typing import Optional

from pydantic import BaseModel, Field


class IngestionRequestV2(BaseModel):
    """Request body for POST /api/ingestion/firms (Module 2)."""

    source: str = Field(
        default="VIIRS_NOAA20_NRT",
        description="FIRMS source ID: VIIRS_NOAA20_NRT or VIIRS_NOAA21_NRT",
    )
    area: str = Field(
        default="world",
        description="Area to query: 'world' or 'xmin,ymin,xmax,ymax'",
    )
    day_range: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of past days to fetch (1-5)",
    )


class IngestionSummary(BaseModel):
    """Response from POST /api/ingestion/firms (Module 2)."""

    source: str = Field(..., description="FIRMS source used")
    fetched: int = Field(default=0, description="Raw records fetched from FIRMS")
    validated: int = Field(default=0, description="Records that passed validation")
    stored: int = Field(default=0, description="New records stored in database")
    duplicates: int = Field(default=0, description="Duplicate records skipped")
    invalid: int = Field(default=0, description="Records that failed validation")
    status: str = Field(default="success", description="success or error")
    error: Optional[str] = Field(default=None, description="Error message if failed")
