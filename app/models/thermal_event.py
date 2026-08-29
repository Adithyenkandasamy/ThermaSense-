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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class ThermalEvent(Base):
    """One VIIRS satellite hotspot pixel from NASA FIRMS."""

    __tablename__ = "thermal_events"

    # ── Primary key ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

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

    # ── FIRMS fire radiometry ──────────────────────────────────────
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    frp: Mapped[float | None] = mapped_column(Float, nullable=True)  # MW
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    satellite: Mapped[str | None] = mapped_column(String(20), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(20), nullable=True)
    daynight: Mapped[str | None] = mapped_column(String(1), nullable=True)  # D/N
    scan: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[float | None] = mapped_column(Float, nullable=True)
    version: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ── Classification ─────────────────────────────────────────────
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risklevel"), nullable=False, default=RiskLevel.LOW
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── AI Summary (from Groq) ─────────────────────────────────────
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

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
    )

    def __repr__(self) -> str:
        return (
            f"<ThermalEvent id={self.id} lat={self.latitude:.4f} "
            f"lon={self.longitude:.4f} risk={self.risk_level} frp={self.frp}>"
        )
