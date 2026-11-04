"""phase1_resource_management

Revision ID: b2c3d4e5f6a7
Revises: 0f610073e5f1
Create Date: 2026-10-31 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '0f610073e5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. study_zones ────────────────────────────────────────────────────────
    op.create_table(
        'study_zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('floor', sa.Integer(), nullable=False),
        sa.Column('total_capacity', sa.Integer(), nullable=False),
        sa.Column('noise_policy', sa.String(length=50), nullable=False, server_default='quiet'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('floor >= 0', name='ck_study_zones_floor_nonneg'),
        sa.CheckConstraint('total_capacity > 0', name='ck_study_zones_capacity_pos'),
        sa.CheckConstraint("noise_policy IN ('silent', 'quiet', 'collaborative')", name='ck_study_zones_noise_policy'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('study_zones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_study_zones_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_study_zones_zone_code'), ['zone_code'], unique=True)

    # ── 2. study_seats ────────────────────────────────────────────────────────
    op.create_table(
        'study_seats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('seat_code', sa.String(length=50), nullable=False),
        sa.Column('has_power_outlet', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('has_monitor', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_accessible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['zone_id'], ['study_zones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('study_seats', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_study_seats_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_study_seats_zone_id'), ['zone_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_study_seats_seat_code'), ['seat_code'], unique=True)

    # ── 3. study_rooms ────────────────────────────────────────────────────────
    op.create_table(
        'study_rooms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('display_type', sa.String(length=50), nullable=True),
        sa.Column('has_whiteboard', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('capacity > 0', name='ck_study_rooms_capacity_pos'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('study_rooms', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_study_rooms_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_study_rooms_room_code'), ['room_code'], unique=True)

    # ── 4. reservations ───────────────────────────────────────────────────────
    op.create_table(
        'reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('seat_id', sa.Integer(), nullable=True),
        sa.Column('room_id', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('end_time > start_time', name='ck_reservations_time_order'),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled', 'no_show')", name='ck_reservations_status_valid'),
        sa.CheckConstraint("resource_type IN ('seat', 'room')", name='ck_reservations_type_valid'),
        sa.CheckConstraint(
            "(resource_type = 'seat' AND seat_id IS NOT NULL AND room_id IS NULL) OR "
            "(resource_type = 'room' AND room_id IS NOT NULL AND seat_id IS NULL)",
            name='ck_reservations_resource_target',
        ),
        sa.ForeignKeyConstraint(['room_id'], ['study_rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seat_id'], ['study_seats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reservations_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_resource_type'), ['resource_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_seat_id'), ['seat_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_room_id'), ['room_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_start_time'), ['start_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_end_time'), ['end_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_reservations_status'), ['status'], unique=False)
        batch_op.create_index('ix_reservations_seat_active_window', ['seat_id', 'status', 'start_time', 'end_time'], unique=False)
        batch_op.create_index('ix_reservations_room_active_window', ['room_id', 'status', 'start_time', 'end_time'], unique=False)
        batch_op.create_index('ix_reservations_user_window', ['user_id', 'start_time', 'end_time'], unique=False)

    # ── 5. occupancy_observations ─────────────────────────────────────────────
    op.create_table(
        'occupancy_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('observed_count', sa.Integer(), nullable=False),
        sa.Column('capacity_utilization', sa.Float(), nullable=False),
        sa.Column('source_sensor_id', sa.String(length=50), nullable=True),
        sa.CheckConstraint('observed_count >= 0', name='ck_occupancy_count_nonneg'),
        sa.CheckConstraint('capacity_utilization >= 0.0', name='ck_occupancy_util_nonneg'),
        sa.ForeignKeyConstraint(['zone_id'], ['study_zones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('occupancy_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_occupancy_observations_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_occupancy_observations_zone_id'), ['zone_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_occupancy_observations_recorded_at'), ['recorded_at'], unique=False)
        batch_op.create_index('ix_occupancy_zone_time', ['zone_id', 'recorded_at'], unique=False)

    # ── 6. search_events ──────────────────────────────────────────────────────
    op.create_table(
        'search_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('query_text', sa.String(length=500), nullable=False),
        sa.Column('search_type', sa.String(length=50), nullable=False, server_default='text'),
        sa.Column('results_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('results_count >= 0', name='ck_search_results_count_nonneg'),
        sa.CheckConstraint('latency_ms >= 0', name='ck_search_latency_nonneg'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('search_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_search_events_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_search_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_search_events_query_text'), ['query_text'], unique=False)
        batch_op.create_index(batch_op.f('ix_search_events_search_type'), ['search_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_search_events_executed_at'), ['executed_at'], unique=False)
        batch_op.create_index('ix_search_events_user_time', ['user_id', 'executed_at'], unique=False)
        batch_op.create_index('ix_search_events_type_time', ['search_type', 'executed_at'], unique=False)

    # ── 7. inventory_events ───────────────────────────────────────────────────
    op.create_table(
        'inventory_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('copy_id', sa.Integer(), nullable=False),
        sa.Column('auditor_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('previous_status', sa.String(length=20), nullable=True),
        sa.Column('new_status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['auditor_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['copy_id'], ['book_copies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('inventory_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inventory_events_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inventory_events_copy_id'), ['copy_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inventory_events_auditor_id'), ['auditor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inventory_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_inventory_events_recorded_at'), ['recorded_at'], unique=False)
        batch_op.create_index('ix_inventory_events_copy_time', ['copy_id', 'recorded_at'], unique=False)
        batch_op.create_index('ix_inventory_events_auditor_time', ['auditor_id', 'recorded_at'], unique=False)

    # ── 8. SQLite Triggers for Interval Overlap Defense-in-Depth ──────────────
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_seat_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status IN ('active', 'confirmed')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND status IN ('active', 'confirmed')
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_seat_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status IN ('active', 'confirmed')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND id != NEW.id
                      AND status IN ('active', 'confirmed')
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
        )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_room_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status IN ('active', 'confirmed')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND status IN ('active', 'confirmed')
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_room_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status IN ('active', 'confirmed')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND id != NEW.id
                      AND status IN ('active', 'confirmed')
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_insert")

    op.drop_table('inventory_events')
    op.drop_table('search_events')
    op.drop_table('occupancy_observations')
    op.drop_table('reservations')
    op.drop_table('study_rooms')
    op.drop_table('study_seats')
    op.drop_table('study_zones')

