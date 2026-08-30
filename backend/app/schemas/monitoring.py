"""
Pydantic schemas for monitoring API endpoints (Module 2).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MonitoringStatusResponse(BaseModel):
    """Response schema for GET /api/monitoring/status."""

    monitoring_enabled: bool = Field(..., description="Whether continuous monitoring is enabled")
    scheduler_running: bool = Field(..., description="Whether the APScheduler is actively running")
    poll_interval_minutes: int = Field(..., description="Polling interval in minutes")
    monitoring_area: str = Field(..., description="Geographic area or bounding box monitored")
    sources: list[str] = Field(..., description="Configured FIRMS sources")
    last_successful_ingestion: Optional[datetime] = Field(
        default=None, description="Timestamp of the last successful ingestion"
    )
    next_scheduled_run: Optional[datetime] = Field(
        default=None, description="Timestamp of the next scheduled run"
    )
    last_ingestion_status: Optional[str] = Field(
        default=None, description="Status of the last ingestion cycle (success, partial_success, failed)"
    )


class IngestionLogItem(BaseModel):
    """Schema representing an individual ingestion run log."""

    id: str = Field(..., description="UUID of the ingestion log")
    source: str = Field(..., description="FIRMS source identifier")
    area: str = Field(..., description="Area queried")
    day_range: int = Field(..., description="Day range queried")
    requested_at: datetime = Field(..., description="When the ingestion was requested/started")
    completed_at: Optional[datetime] = Field(default=None, description="When the ingestion completed")
    status: str = Field(..., description="Run status: pending, success, partial, error")
    records_fetched: int = Field(default=0, description="Number of raw records fetched")
    records_validated: int = Field(default=0, description="Number of records successfully validated")
    records_stored: int = Field(default=0, description="Number of new records stored")
    duplicates_skipped: int = Field(default=0, description="Number of duplicate records skipped")
    invalid_records: int = Field(default=0, description="Number of malformed records rejected")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")


class MonitoringLogsResponse(BaseModel):
    """Response schema for GET /api/monitoring/logs."""

    total: int = Field(..., description="Total number of matching log entries")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Pagination offset")
    logs: list[IngestionLogItem] = Field(..., description="List of ingestion log entries")


class MonitoringRunResponse(BaseModel):
    """Response schema for POST /api/monitoring/run."""

    status: str = Field(..., description="Outcome status of the manual run trigger")
    timestamp: Optional[str] = Field(default=None, description="Execution timestamp")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Per-source ingestion results")
