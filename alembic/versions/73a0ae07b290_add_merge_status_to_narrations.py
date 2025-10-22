"""Add merge status to narrations

Revision ID: 73a0ae07b290
Revises: c1a2b3d4e5f6
Create Date: 2025-10-05 14:40:31.041359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '73a0ae07b290'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cria o novo tipo ENUM no PostgreSQL antes de usá-lo.
    merge_status_enum = postgresql.ENUM('MERGE_PENDING', 'MERGE_PROCESSING', 'MERGE_COMPLETED', 'MERGE_FAILED', name='merge_status_enum')
    merge_status_enum.create(op.get_bind())

    # Adiciona as colunas na tabela 'narrations' usando o novo tipo ENUM.
    with op.batch_alter_table('narrations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('merge_status', sa.Enum('MERGE_PENDING', 'MERGE_PROCESSING', 'MERGE_COMPLETED', 'MERGE_FAILED', name='merge_status_enum'), nullable=True))
        batch_op.add_column(sa.Column('result_video_path', sa.String(length=2048), nullable=True))
        batch_op.add_column(sa.Column('merge_error_details', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_narrations_merge_status'), ['merge_status'], unique=False)


def downgrade() -> None:
    # Remove as colunas e o índice da tabela 'narrations'.
    with op.batch_alter_table('narrations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_narrations_merge_status'))
        batch_op.drop_column('merge_error_details')
        batch_op.drop_column('result_video_path')
        batch_op.drop_column('merge_status')

    # Remove o tipo ENUM do banco de dados.
    merge_status_enum = postgresql.ENUM('MERGE_PENDING', 'MERGE_PROCESSING', 'MERGE_COMPLETED', 'MERGE_FAILED', name='merge_status_enum')
    merge_status_enum.drop(op.get_bind())