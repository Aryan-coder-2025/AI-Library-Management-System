"""knowledge representation tables

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-11-05 03:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. subjects table
    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name')
    )
    with op.batch_alter_table('subjects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subjects_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_subjects_name'), ['name'], unique=True)
        batch_op.create_index(batch_op.f('ix_subjects_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_subjects_parent_id'), ['parent_id'], unique=False)

    # 2. topics table
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subject_id', 'name', name='uq_topic_subject_name')
    )
    with op.batch_alter_table('topics', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_topics_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_topics_subject_id'), ['subject_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_topics_name'), ['name'], unique=False)

    # 3. concepts table
    op.create_table(
        'concepts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_id', 'name', name='uq_concept_topic_name')
    )
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concepts_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_concepts_topic_id'), ['topic_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_concepts_name'), ['name'], unique=False)

    # 4. book_subjects table
    op.create_table(
        'book_subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'subject_id', name='uq_book_subject')
    )
    with op.batch_alter_table('book_subjects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_book_subjects_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_subjects_book_id'), ['book_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_subjects_subject_id'), ['subject_id'], unique=False)

    # 5. book_topics table
    op.create_table(
        'book_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'topic_id', name='uq_book_topic')
    )
    with op.batch_alter_table('book_topics', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_book_topics_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_topics_book_id'), ['book_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_topics_topic_id'), ['topic_id'], unique=False)

    # 6. book_concepts table
    op.create_table(
        'book_concepts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('concept_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'concept_id', name='uq_book_concept')
    )
    with op.batch_alter_table('book_concepts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_book_concepts_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_concepts_book_id'), ['book_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_book_concepts_concept_id'), ['concept_id'], unique=False)


def downgrade() -> None:
    op.drop_table('book_concepts')
    op.drop_table('book_topics')
    op.drop_table('book_subjects')
    op.drop_table('concepts')
    op.drop_table('topics')
    op.drop_table('subjects')

