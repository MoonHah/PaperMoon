"""add content_hash to documents

Revision ID: b7d2e9f4a3c1
Revises: 94c479ca6dcd
Create Date: 2026-06-11 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d2e9f4a3c1'
down_revision: Union[str, Sequence[str], None] = '94c479ca6dcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('content_hash', sa.String(), nullable=True))
    op.create_index('ix_documents_content_hash', 'documents', ['content_hash'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_documents_content_hash', table_name='documents')
    op.drop_column('documents', 'content_hash')
