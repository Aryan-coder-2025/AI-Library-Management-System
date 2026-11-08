"""spatial subsystem tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-05 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. library_floors table
    op.create_table(
        'library_floors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('floor_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('width', sa.Float(), nullable=False, server_default='1000.0'),
        sa.Column('height', sa.Float(), nullable=False, server_default='700.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('published_layout_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('floor_number', name='uq_library_floors_number')
    )
    with op.batch_alter_table('library_floors', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_library_floors_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_library_floors_floor_number'), ['floor_number'], unique=True)

    # 2. floor_plans table
    op.create_table(
        'floor_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('floor_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('svg_viewbox', sa.String(length=50), nullable=False, server_default='0 0 1000 700'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name='ck_floor_plans_status'),
        sa.ForeignKeyConstraint(['floor_id'], ['library_floors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('floor_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_floor_plans_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_floor_plans_floor_id'), ['floor_id'], unique=False)
        batch_op.create_index('ix_floor_plans_floor_status', ['floor_id', 'status'], unique=False)

    # Add foreign key constraint on library_floors.published_layout_id pointing to floor_plans.id
    with op.batch_alter_table('library_floors', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_library_floors_published_layout_id',
            'floor_plans',
            ['published_layout_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # 3. floor_plan_elements table
    op.create_table(
        'floor_plan_elements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('floor_id', sa.Integer(), nullable=False),
        sa.Column('layout_id', sa.Integer(), nullable=True),
        sa.Column('element_type', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('geometry_type', sa.String(length=20), nullable=False),
        sa.Column('geometry_data', sa.JSON(), nullable=False),
        sa.Column('style_properties', sa.JSON(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['floor_id'], ['library_floors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['layout_id'], ['floor_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('floor_plan_elements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_floor_plan_elements_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_floor_plan_elements_floor_id'), ['floor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_floor_plan_elements_layout_id'), ['layout_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_floor_plan_elements_element_type'), ['element_type'], unique=False)

    # 4. spatial_resource_mappings table
    op.create_table(
        'spatial_resource_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('floor_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('width', sa.Float(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('rotation', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("resource_type IN ('zone', 'room', 'seat')", name='ck_spatial_resource_type'),
        sa.CheckConstraint("x >= 0.0 AND x <= 1.05", name='ck_spatial_mapping_x_bounds'),
        sa.CheckConstraint("y >= 0.0 AND y <= 1.05", name='ck_spatial_mapping_y_bounds'),
        sa.ForeignKeyConstraint(['floor_id'], ['library_floors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_type', 'resource_id', name='uq_spatial_resource_mapping')
    )
    with op.batch_alter_table('spatial_resource_mappings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_spatial_resource_mappings_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_spatial_resource_mappings_floor_id'), ['floor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_spatial_resource_mappings_resource_type'), ['resource_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_spatial_resource_mappings_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index('ix_spatial_mappings_floor_type', ['floor_id', 'resource_type'], unique=False)

    # 5. wayfinding_nodes table
    op.create_table(
        'wayfinding_nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('floor_id', sa.Integer(), nullable=False),
        sa.Column('node_type', sa.String(length=30), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['floor_id'], ['library_floors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('wayfinding_nodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_wayfinding_nodes_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_wayfinding_nodes_floor_id'), ['floor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_wayfinding_nodes_node_type'), ['node_type'], unique=False)

    # 6. wayfinding_edges table
    op.create_table(
        'wayfinding_edges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_node_id', sa.Integer(), nullable=False),
        sa.Column('to_node_id', sa.Integer(), nullable=False),
        sa.Column('distance', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_accessible', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('edge_type', sa.String(length=20), nullable=False, server_default='walkway'),
        sa.ForeignKeyConstraint(['from_node_id'], ['wayfinding_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_node_id'], ['wayfinding_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('wayfinding_edges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_wayfinding_edges_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_wayfinding_edges_from_node_id'), ['from_node_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_wayfinding_edges_to_node_id'), ['to_node_id'], unique=False)


def downgrade() -> None:
    # Drop wayfinding tables
    op.drop_table('wayfinding_edges')
    op.drop_table('wayfinding_nodes')

    # Drop spatial resource mappings
    op.drop_table('spatial_resource_mappings')

    # Drop elements
    op.drop_table('floor_plan_elements')

    # Remove foreign key from library_floors before dropping floor_plans
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        with op.batch_alter_table('library_floors', schema=None) as batch_op:
            batch_op.drop_constraint('fk_library_floors_published_layout_id', type_='foreignkey')

    # Drop floor_plans
    op.drop_table('floor_plans')

    # Drop library_floors
    op.drop_table('library_floors')

