"""add data_subject_requests

Revision ID: a3c9d2e7b410
Revises: 1f9243cb48b3
Create Date: 2026-10-16 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c9d2e7b410'
down_revision: Union[str, Sequence[str], None] = '1f9243cb48b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'data_subject_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('region', sa.String(), nullable=True),
        sa.Column('request_type', sa.String(), nullable=True),
        sa.Column('regulations', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('extension_noticed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_event_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_data_subject_requests_id'), 'data_subject_requests', ['id'], unique=False)
    op.create_index(op.f('ix_data_subject_requests_request_id'), 'data_subject_requests', ['request_id'], unique=True)
    op.create_index(op.f('ix_data_subject_requests_user_id'), 'data_subject_requests', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_data_subject_requests_user_id'), table_name='data_subject_requests')
    op.drop_index(op.f('ix_data_subject_requests_request_id'), table_name='data_subject_requests')
    op.drop_index(op.f('ix_data_subject_requests_id'), table_name='data_subject_requests')
    op.drop_table('data_subject_requests')
