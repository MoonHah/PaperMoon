"""add user_id to documents (multi-tenant)

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-06-16 10:30:00.000000

清库重来：现有文档无归属用户（多为开发期测试数据），先清空再加 NOT NULL 的 user_id。
注意：Qdrant 向量需另行清空（删除并重建 collection），不在本迁移内。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b3c4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM documents")  # 清库：旧数据无主
    op.add_column('documents', sa.Column('user_id', sa.String(), nullable=False))
    op.create_foreign_key(
        'fk_documents_user_id', 'documents', 'users', ['user_id'], ['id']
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_constraint('fk_documents_user_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'user_id')
