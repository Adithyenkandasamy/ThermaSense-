"""
ThermalEvent ORM model.

Maps to the `thermal_events` table in PostgreSQL/PostGIS.
Each row represents one satellite-detected hotspot (VIIRS pixel).
"""

import enum
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class EventClassification(str, enum.Enum):
    INDUSTRIAL_THERMAL = "INDUSTRIAL_THERMAL"
    WILDFIRE = "WILDFIRE"
    AGRICULTURAL_BURNING = "AGRICULTURAL_BURNING"
    MINING_ACTIVITY = "MINING_ACTIVITY"
    OTHER_THERMAL_SOURCE = "OTHER_THERMAL_SOURCE"
    UNKNOWN = "UNKNOWN"


class ThermalEvent(Base):
    """One VIIRS satellite hotspot pixel from NASA FIRMS."""

    __tablename__ = "thermal_events"

    # ── Primary key ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="VIIRS_SNPP_NRT")

    # ── Spatial ────────────────────────────────────────────────────
    # PostGIS POINT geometry in WGS84 (EPSG:4326)
    # spatial_index=False because we define it explicitly in __table_args__
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Temporal ───────────────────────────────────────────────────
    acq_date: Mapped[date] = mapped_column(Date, nullable=False)
    acq_time: Mapped[str] = mapped_column(String(4), nullable=False)  # "HHMM"
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── FIRMS fire radiometry ──────────────────────────────────────
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    frp: Mapped[float | None] = mapped_column(Float, nullable=True)  # MW
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    satellite: Mapped[str | None] = mapped_column(String(20), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(20), nullable=True)
    daynight: Mapped[str | None] = mapped_column(String(1), nullable=True)  # D/N
    day_night: Mapped[str | None] = mapped_column(String(1), nullable=True)
    scan: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[float | None] = mapped_column(Float, nullable=True)
    version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Classification ─────────────────────────────────────────────
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risklevel"), nullable=False, default=RiskLevel.LOW
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── AI Summary (from Groq) ─────────────────────────────────────
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    analysis: Mapped["EventAnalysis | None"] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # ── Metadata ───────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Constraints ────────────────────────────────────────────────
    __table_args__ = (
        # Prevent duplicate hotspot rows for the same pixel/time
        UniqueConstraint("latitude", "longitude", "acq_date", "acq_time", name="uq_hotspot"),
        # Spatial index — powers bbox queries
        Index("idx_thermal_events_geom", "geom", postgresql_using="gist"),
        # Temporal index
        Index("idx_thermal_events_acq_date", "acq_date"),
        # Risk level index for filtering
        Index("idx_thermal_events_risk_level", "risk_level"),
        Index("idx_thermal_events_observed_at", "observed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ThermalEvent id={self.id} lat={self.latitude:.4f} "
            f"lon={self.longitude:.4f} risk={self.risk_level} frp={self.frp}>"
        )


class IndustrialFacility(Base):
    """Open geospatial industrial context near thermal events."""

    __tablename__ = "industrial_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(80), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")
    facility_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_industrial_facilities_geom", "geom", postgresql_using="gist"),
        Index("idx_industrial_facilities_type", "facility_type"),
    )


class EventAnalysis(Base):
    """Stored contextual investigation for one thermal event."""

    __tablename__ = "event_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("thermal_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    classification: Mapped[EventClassification] = mapped_column(
        Enum(EventClassification, name="eventclassification"),
        nullable=False,
        default=EventClassification.UNKNOWN,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risklevel", create_type=False),
        nullable=False,
        default=RiskLevel.LOW,
    )
    persistence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    industrial_context_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False, default="demo-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event: Mapped[ThermalEvent] = relationship(back_populates="analysis")

    __table_args__ = (
        Index("idx_event_analysis_risk_level", "risk_level"),
        Index("idx_event_analysis_classification", "classification"),
    )
