"""add setup/emotion tags and daily risk limit

Revision ID: c3d8f1a0b2e4
Revises: 8f2c1a9d4b6e
Create Date: 2026-10-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d8f1a0b2e4'
down_revision: Union[str, None] = '8f2c1a9d4b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trades', sa.Column('setup_tag', sa.String(length=32), nullable=True))
    op.add_column('trades', sa.Column('emotion_tag', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('daily_risk_limit', sa.Numeric(10, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'daily_risk_limit')
    op.drop_column('trades', 'emotion_tag')
    op.drop_column('trades', 'setup_tag')
