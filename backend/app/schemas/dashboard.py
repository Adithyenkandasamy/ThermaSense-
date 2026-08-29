"""Dashboard summary schemas."""

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    active_events: int
    high_risk: int
    extreme_risk: int
    api_status: str
    database_status: str
    demo_mode: bool
