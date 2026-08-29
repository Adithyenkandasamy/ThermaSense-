"""create_thermal_events

Revision ID: 5ab37e2636ac
Revises: 
Create Date: 2026-08-29 16:15:05.591997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '5ab37e2636ac'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create thermal_events table and spatial indexes."""
    bind = op.get_bind()
    
    # Check if the enum type 'risklevel' already exists
    result = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risklevel')"))
    enum_exists = result.scalar()

    if not enum_exists:
        op.execute("CREATE TYPE risklevel AS ENUM ('LOW', 'MODERATE', 'HIGH', 'EXTREME')")

    # Define enum type with create_type=False to avoid automatic creation attempts
    risk_level_enum = postgresql.ENUM(
        'LOW', 'MODERATE', 'HIGH', 'EXTREME',
        name='risklevel',
        create_type=False
    )

    op.create_table(
        'thermal_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'geom',
            geoalchemy2.types.Geometry(
                geometry_type='POINT',
                srid=4326,
                dimension=2,
                from_text='ST_GeomFromEWKT',
                name='geometry',
                nullable=False,
                spatial_index=False
            ),
            nullable=False
        ),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('acq_date', sa.Date(), nullable=False),
        sa.Column('acq_time', sa.String(length=4), nullable=False),
        sa.Column('brightness', sa.Float(), nullable=True),
        sa.Column('frp', sa.Float(), nullable=True),
        sa.Column('confidence', sa.String(length=10), nullable=True),
        sa.Column('satellite', sa.String(length=20), nullable=True),
        sa.Column('instrument', sa.String(length=20), nullable=True),
        sa.Column('daynight', sa.String(length=1), nullable=True),
        sa.Column('scan', sa.Float(), nullable=True),
        sa.Column('track', sa.Float(), nullable=True),
        sa.Column('version', sa.String(length=10), nullable=True),
        sa.Column('risk_level', risk_level_enum, nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('ai_generated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('latitude', 'longitude', 'acq_date', 'acq_time', name='uq_hotspot')
    )
    op.create_index('idx_thermal_events_acq_date', 'thermal_events', ['acq_date'], unique=False)
    op.create_index('idx_thermal_events_geom', 'thermal_events', ['geom'], unique=False, postgresql_using='gist')
    op.create_index('idx_thermal_events_risk_level', 'thermal_events', ['risk_level'], unique=False)


def downgrade() -> None:
    """Drop thermal_events table and spatial indexes."""
    op.drop_index('idx_thermal_events_risk_level', table_name='thermal_events')
    op.drop_index('idx_thermal_events_geom', table_name='thermal_events', postgresql_using='gist')
    op.drop_index('idx_thermal_events_acq_date', table_name='thermal_events')
    op.drop_table('thermal_events')
    
    # Drop enum
    op.execute("DROP TYPE IF EXISTS risklevel")
