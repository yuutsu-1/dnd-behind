"""add character_skills

Revision ID: a7d3e91b4c52
Revises: c1fcfd7fe014
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7d3e91b4c52'
down_revision: Union[str, None] = 'c1fcfd7fe014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('character_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('expertise', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skill_definitions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'skill_id')
    )


def downgrade() -> None:
    op.drop_table('character_skills')
