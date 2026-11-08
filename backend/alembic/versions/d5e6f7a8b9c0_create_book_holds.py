"""create book_holds table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-11-08 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'book_holds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('copy_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='waiting', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('allocated_at', sa.DateTime(), nullable=True),
        sa.Column('pickup_expires_at', sa.DateTime(), nullable=True),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['copy_id'], ['book_copies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_book_holds_id', 'book_holds', ['id'], unique=False)
    op.create_index('ix_book_holds_book_id', 'book_holds', ['book_id'], unique=False)
    op.create_index('ix_book_holds_user_id', 'book_holds', ['user_id'], unique=False)
    op.create_index('ix_book_holds_copy_id', 'book_holds', ['copy_id'], unique=False)
    op.create_index('ix_book_holds_status', 'book_holds', ['status'], unique=False)
    op.create_index('ix_book_holds_created_at', 'book_holds', ['created_at'], unique=False)
    op.create_index('ix_book_holds_pickup_expires_at', 'book_holds', ['pickup_expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_book_holds_pickup_expires_at', table_name='book_holds')
    op.drop_index('ix_book_holds_created_at', table_name='book_holds')
    op.drop_index('ix_book_holds_status', table_name='book_holds')
    op.drop_index('ix_book_holds_copy_id', table_name='book_holds')
    op.drop_index('ix_book_holds_user_id', table_name='book_holds')
    op.drop_index('ix_book_holds_book_id', table_name='book_holds')
    op.drop_index('ix_book_holds_id', table_name='book_holds')
    op.drop_table('book_holds')

