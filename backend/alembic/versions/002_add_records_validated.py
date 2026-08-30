"""add records_validated to ingestion_logs

Revision ID: 002_add_records_validated
Revises: 001_initial_schema
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_records_validated'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ingestion_logs',
        sa.Column('records_validated', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('ingestion_logs', 'records_validated')
