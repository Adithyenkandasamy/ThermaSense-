"""add_context_analysis_tables

Revision ID: 9c4b6f1d2a03
Revises: 5ab37e2636ac
Create Date: 2026-08-29 18:12:00.000000

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c4b6f1d2a03"
down_revision: Union[str, Sequence[str], None] = "5ab37e2636ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column)"
        ),
        {"table": table, "column": column.name},
    ).scalar()
    if not exists:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()

    enum_exists = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eventclassification')")
    ).scalar()
    if not enum_exists:
        op.execute(
            "CREATE TYPE eventclassification AS ENUM "
            "('INDUSTRIAL_THERMAL', 'WILDFIRE', 'AGRICULTURAL_BURNING', "
            "'MINING_ACTIVITY', 'OTHER_THERMAL_SOURCE', 'UNKNOWN')"
        )

    classification_enum = postgresql.ENUM(
        "INDUSTRIAL_THERMAL",
        "WILDFIRE",
        "AGRICULTURAL_BURNING",
        "MINING_ACTIVITY",
        "OTHER_THERMAL_SOURCE",
        "UNKNOWN",
        name="eventclassification",
        create_type=False,
    )
    risk_level_enum = postgresql.ENUM(
        "LOW", "MODERATE", "HIGH", "EXTREME", name="risklevel", create_type=False
    )

    _add_column_if_missing("thermal_events", sa.Column("external_id", sa.String(160), nullable=True))
    _add_column_if_missing(
        "thermal_events",
        sa.Column("source", sa.String(40), nullable=False, server_default="VIIRS_SNPP_NRT"),
    )
    _add_column_if_missing(
        "thermal_events", sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True)
    )
    _add_column_if_missing("thermal_events", sa.Column("day_night", sa.String(1), nullable=True))
    _add_column_if_missing("thermal_events", sa.Column("raw_data", sa.JSON(), nullable=True))

    op.create_index(
        "idx_thermal_events_observed_at", "thermal_events", ["observed_at"], unique=False, if_not_exists=True
    )
    op.create_index(
        "uq_thermal_events_external_id",
        "thermal_events",
        ["external_id"],
        unique=True,
        if_not_exists=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "industrial_facilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(160), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("facility_type", sa.String(80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="POINT", srid=4326, dimension=2, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(80), nullable=False, server_default="DEMO"),
        sa.Column("facility_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_industrial_facilities_external_id"),
    )
    op.create_index(
        "idx_industrial_facilities_geom",
        "industrial_facilities",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index("idx_industrial_facilities_type", "industrial_facilities", ["facility_type"])

    op.create_table(
        "event_analysis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("classification", classification_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("persistence_score", sa.Float(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("industrial_context_score", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False, server_default="demo-v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["thermal_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_event_analysis_event_id"),
    )
    op.create_index("idx_event_analysis_risk_level", "event_analysis", ["risk_level"])
    op.create_index("idx_event_analysis_classification", "event_analysis", ["classification"])


def downgrade() -> None:
    op.drop_index("idx_event_analysis_classification", table_name="event_analysis")
    op.drop_index("idx_event_analysis_risk_level", table_name="event_analysis")
    op.drop_table("event_analysis")
    op.drop_index("idx_industrial_facilities_type", table_name="industrial_facilities")
    op.drop_index("idx_industrial_facilities_geom", table_name="industrial_facilities", postgresql_using="gist")
    op.drop_table("industrial_facilities")
    op.drop_index("uq_thermal_events_external_id", table_name="thermal_events")
    op.drop_index("idx_thermal_events_observed_at", table_name="thermal_events")
    op.drop_column("thermal_events", "raw_data")
    op.drop_column("thermal_events", "day_night")
    op.drop_column("thermal_events", "observed_at")
    op.drop_column("thermal_events", "source")
    op.drop_column("thermal_events", "external_id")
    op.execute("DROP TYPE IF EXISTS eventclassification")
