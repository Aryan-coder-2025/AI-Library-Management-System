"""add academic reserves collection and acquisitions

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-11-08 21:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. courses
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=False),
        sa.Column('term', sa.String(length=50), nullable=False),
        sa.Column('instructor_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['instructor_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_courses_id', 'courses', ['id'], unique=False)
    op.create_index('ix_courses_code', 'courses', ['code'], unique=True)
    op.create_index('ix_courses_department', 'courses', ['department'], unique=False)
    op.create_index('ix_courses_instructor_id', 'courses', ['instructor_id'], unique=False)

    # 2. course_reading_list_items
    op.create_table(
        'course_reading_list_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('added_by_id', sa.Integer(), nullable=False),
        sa.Column('requirement_type', sa.String(length=50), server_default='required', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('course_id', 'book_id', name='uq_course_book_reading_list'),
    )
    op.create_index('ix_course_reading_list_items_id', 'course_reading_list_items', ['id'], unique=False)
    op.create_index('ix_course_reading_list_items_course_id', 'course_reading_list_items', ['course_id'], unique=False)
    op.create_index('ix_course_reading_list_items_book_id', 'course_reading_list_items', ['book_id'], unique=False)

    # 3. course_reserves
    op.create_table(
        'course_reserves',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('copy_id', sa.Integer(), nullable=False),
        sa.Column('reserve_type', sa.String(length=20), server_default='2_hour', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['copy_id'], ['book_copies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('copy_id', name='uq_course_reserve_copy'),
    )
    op.create_index('ix_course_reserves_id', 'course_reserves', ['id'], unique=False)
    op.create_index('ix_course_reserves_course_id', 'course_reserves', ['course_id'], unique=False)
    op.create_index('ix_course_reserves_copy_id', 'course_reserves', ['copy_id'], unique=True)

    # 4. book_collection_tokens
    op.create_table(
        'book_collection_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hold_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['hold_id'], ['book_holds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_book_collection_tokens_id', 'book_collection_tokens', ['id'], unique=False)
    op.create_index('ix_book_collection_tokens_hold_id', 'book_collection_tokens', ['hold_id'], unique=False)
    op.create_index('ix_book_collection_tokens_user_id', 'book_collection_tokens', ['user_id'], unique=False)
    op.create_index('ix_book_collection_tokens_token_hash', 'book_collection_tokens', ['token_hash'], unique=True)
    op.create_index('ix_book_collection_tokens_expires_at', 'book_collection_tokens', ['expires_at'], unique=False)

    # 5. acquisition_requests
    op.create_table(
        'acquisition_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('suggested_title', sa.String(length=255), nullable=False),
        sa.Column('suggested_author', sa.String(length=255), nullable=True),
        sa.Column('isbn', sa.String(length=20), nullable=True),
        sa.Column('search_query_origin', sa.String(length=255), nullable=True),
        sa.Column('frequency_score', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='suggested', nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_acquisition_requests_id', 'acquisition_requests', ['id'], unique=False)
    op.create_index('ix_acquisition_requests_suggested_title', 'acquisition_requests', ['suggested_title'], unique=False)
    op.create_index('ix_acquisition_requests_isbn', 'acquisition_requests', ['isbn'], unique=False)
    op.create_index('ix_acquisition_requests_status', 'acquisition_requests', ['status'], unique=False)
    op.create_index('ix_acquisition_requests_created_at', 'acquisition_requests', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_acquisition_requests_created_at', table_name='acquisition_requests')
    op.drop_index('ix_acquisition_requests_status', table_name='acquisition_requests')
    op.drop_index('ix_acquisition_requests_isbn', table_name='acquisition_requests')
    op.drop_index('ix_acquisition_requests_suggested_title', table_name='acquisition_requests')
    op.drop_index('ix_acquisition_requests_id', table_name='acquisition_requests')
    op.drop_table('acquisition_requests')

    op.drop_index('ix_book_collection_tokens_expires_at', table_name='book_collection_tokens')
    op.drop_index('ix_book_collection_tokens_token_hash', table_name='book_collection_tokens')
    op.drop_index('ix_book_collection_tokens_user_id', table_name='book_collection_tokens')
    op.drop_index('ix_book_collection_tokens_hold_id', table_name='book_collection_tokens')
    op.drop_index('ix_book_collection_tokens_id', table_name='book_collection_tokens')
    op.drop_table('book_collection_tokens')

    op.drop_index('ix_course_reserves_copy_id', table_name='course_reserves')
    op.drop_index('ix_course_reserves_course_id', table_name='course_reserves')
    op.drop_index('ix_course_reserves_id', table_name='course_reserves')
    op.drop_table('course_reserves')

    op.drop_index('ix_course_reading_list_items_book_id', table_name='course_reading_list_items')
    op.drop_index('ix_course_reading_list_items_course_id', table_name='course_reading_list_items')
    op.drop_index('ix_course_reading_list_items_id', table_name='course_reading_list_items')
    op.drop_table('course_reading_list_items')

    op.drop_index('ix_courses_instructor_id', table_name='courses')
    op.drop_index('ix_courses_department', table_name='courses')
    op.drop_index('ix_courses_code', table_name='courses')
    op.drop_index('ix_courses_id', table_name='courses')
    op.drop_table('courses')

