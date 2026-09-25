"""add margin presets table

Revision ID: 8f2c1a9d4b6e
Revises: 4a43c7763433
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8f2c1a9d4b6e'
down_revision: Union[str, None] = '4a43c7763433'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'margin_presets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Numeric(20, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_margin_presets_user_id', 'margin_presets', ['user_id'])

    # Every existing user already has a single margin value (users.margin,
    # default 500) - carry it forward as their first preset so nobody's
    # current leverage calculations change or disappear after this upgrade.
    op.execute(
        """
        INSERT INTO margin_presets (user_id, label, amount)
        SELECT id, 'Margin', margin FROM users
        """
    )


def downgrade() -> None:
    op.drop_index('ix_margin_presets_user_id', table_name='margin_presets')
    op.drop_table('margin_presets')
