"""add thermal_events table and event_id FK on observations

Revision ID: 003_add_thermal_events
Revises: 002_add_records_validated
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '003_add_thermal_events'
down_revision: Union[str, None] = '002_add_records_validated'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create the thermal_events table ──────────────────────────
    op.create_table(
        'thermal_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            sa.String(length=10),
            nullable=False,
            server_default='active',
            comment="Event status: 'active' or 'inactive'",
        ),
        sa.Column(
            'centroid_latitude',
            sa.Float(),
            nullable=False,
            comment='Centroid latitude in WGS84',
        ),
        sa.Column(
            'centroid_longitude',
            sa.Float(),
            nullable=False,
            comment='Centroid longitude in WGS84',
        ),
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='UTC timestamp when the event was first detected',
        ),
        sa.Column(
            'ended_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='UTC timestamp when the event was last detected',
        ),
        sa.Column(
            'total_frp',
            sa.Float(),
            nullable=True,
            server_default='0.0',
            comment='Sum of FRP across all linked observations (MW)',
        ),
        sa.Column(
            'max_confidence',
            sa.String(length=10),
            nullable=True,
            comment='Highest confidence level among linked observations',
        ),
        sa.Column(
            'observation_count',
            sa.Float(),
            nullable=False,
            server_default='0',
            comment='Number of observations linked to this event',
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
            comment='Optional human-readable description',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Indexes on thermal_events ────────────────────────────────
    op.create_index('ix_event_started_at', 'thermal_events', ['started_at'])
    op.create_index('ix_event_status', 'thermal_events', ['status'])
    op.create_index(
        'ix_event_centroid',
        'thermal_events',
        ['centroid_latitude', 'centroid_longitude'],
    )

    # ── Add nullable event_id FK to thermal_observations ─────────
    op.add_column(
        'thermal_observations',
        sa.Column('event_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_observation_event_id',
        'thermal_observations',
        'thermal_events',
        ['event_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_observation_event_id',
        'thermal_observations',
        ['event_id'],
    )


def downgrade() -> None:
    # ── Remove event_id from thermal_observations ────────────────
    op.drop_index('ix_observation_event_id', table_name='thermal_observations')
    op.drop_constraint(
        'fk_observation_event_id',
        'thermal_observations',
        type_='foreignkey',
    )
    op.drop_column('thermal_observations', 'event_id')

    # ── Drop thermal_events indexes and table ────────────────────
    op.drop_index('ix_event_centroid', table_name='thermal_events')
    op.drop_index('ix_event_status', table_name='thermal_events')
    op.drop_index('ix_event_started_at', table_name='thermal_events')
    op.drop_table('thermal_events')
