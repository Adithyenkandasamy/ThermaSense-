"""create thermal_observations and ingestion_logs tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Table: thermal_observations ───────────────────────────────────────
    op.create_table(
        'thermal_observations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, comment='FIRMS source ID, e.g. VIIRS_NOAA20_NRT'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('acquisition_datetime', sa.DateTime(timezone=True), nullable=False, comment='UTC acquisition timestamp'),
        sa.Column('acq_date', sa.String(length=10), nullable=False, comment='Original FIRMS acq_date (YYYY-MM-DD)'),
        sa.Column('acq_time', sa.String(length=4), nullable=False, comment='Original FIRMS acq_time (HHMM)'),
        sa.Column('satellite', sa.String(length=30), nullable=False, comment='Satellite name, e.g. N20 or NOAA-20'),
        sa.Column('instrument', sa.String(length=20), nullable=False, comment='Instrument name, e.g. VIIRS'),
        sa.Column('brightness', sa.Float(), nullable=True, comment='Brightness temperature (K)'),
        sa.Column('bright_ti4', sa.Float(), nullable=True, comment='VIIRS I-4 channel brightness temperature (K)'),
        sa.Column('bright_ti5', sa.Float(), nullable=True, comment='VIIRS I-5 channel brightness temperature (K)'),
        sa.Column('frp', sa.Float(), nullable=True, comment='Fire Radiative Power (MW)'),
        sa.Column('confidence', sa.String(length=10), nullable=True, comment='Detection confidence (low, nominal, high)'),
        sa.Column('daynight', sa.String(length=1), nullable=True, comment='Day or night detection (D/N)'),
        sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Original FIRMS CSV row as JSON for traceability'),
        sa.Column('observation_hash', sa.String(length=64), nullable=False, comment='SHA-256 hash of identity fields for deduplication'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('observation_hash', name='uq_observation_hash'),
    )
    op.create_index(op.f('ix_thermal_observations_acquisition_datetime'), 'thermal_observations', ['acquisition_datetime'], unique=False)
    op.create_index(op.f('ix_thermal_observations_observation_hash'), 'thermal_observations', ['observation_hash'], unique=True)
    op.create_index(op.f('ix_thermal_observations_satellite'), 'thermal_observations', ['satellite'], unique=False)
    op.create_index(op.f('ix_thermal_observations_source'), 'thermal_observations', ['source'], unique=False)
    op.create_index('ix_acq_datetime_source', 'thermal_observations', ['acquisition_datetime', 'source'], unique=False)
    op.create_index('ix_lat_lon', 'thermal_observations', ['latitude', 'longitude'], unique=False)

    # ── Table: ingestion_logs ─────────────────────────────────────────────
    op.create_table(
        'ingestion_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, comment='FIRMS source ID used'),
        sa.Column('area', sa.String(length=100), nullable=False, comment='Area queried (world or bbox)'),
        sa.Column('day_range', sa.Integer(), nullable=False, comment='Number of days queried (1-5)'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, comment='pending, success, partial, error'),
        sa.Column('records_fetched', sa.Integer(), nullable=False),
        sa.Column('records_stored', sa.Integer(), nullable=False),
        sa.Column('duplicates_skipped', sa.Integer(), nullable=False),
        sa.Column('invalid_records', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error details if status is error'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('ingestion_logs')
    op.drop_index('ix_lat_lon', table_name='thermal_observations')
    op.drop_index('ix_acq_datetime_source', table_name='thermal_observations')
    op.drop_index(op.f('ix_thermal_observations_source'), table_name='thermal_observations')
    op.drop_index(op.f('ix_thermal_observations_satellite'), table_name='thermal_observations')
    op.drop_index(op.f('ix_thermal_observations_observation_hash'), table_name='thermal_observations')
    op.drop_index(op.f('ix_thermal_observations_acquisition_datetime'), table_name='thermal_observations')
    op.drop_table('thermal_observations')
