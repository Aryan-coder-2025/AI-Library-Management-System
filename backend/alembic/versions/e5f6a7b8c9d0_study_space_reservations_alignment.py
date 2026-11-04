"""study space reservations alignment

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-01 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add checked_in_at, expected_attendees, actual_attendees to reservations
    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('checked_in_at', sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('expected_attendees', sa.Integer(), nullable=False, server_default='1')
        )
        batch_op.add_column(
            sa.Column('actual_attendees', sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            batch_op.f('ix_reservations_checked_in_at'), ['checked_in_at'], unique=False
        )

    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        # Re-ensure the 4 resource collision triggers (since SQLite table recreation drops them)
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_update")

        op.execute("""
        CREATE TRIGGER trg_prevent_seat_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_seat_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND id != NEW.id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_room_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_room_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND id != NEW.id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)

        # Add new NULL-safe user-overlap triggers
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_user_reservation_overlap_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_user_reservation_overlap_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_role_demotion_with_overlapping_reservations")

        op.execute("""
        CREATE TRIGGER trg_prevent_user_reservation_overlap_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.status = 'active'
         AND COALESCE((SELECT role FROM users WHERE id = NEW.user_id), '') NOT IN ('librarian', 'admin')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE user_id = NEW.user_id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: user already has an active reservation during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_user_reservation_overlap_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.status = 'active'
         AND COALESCE((SELECT role FROM users WHERE id = NEW.user_id), '') NOT IN ('librarian', 'admin')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE user_id = NEW.user_id
                      AND id != NEW.id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: user already has an active reservation during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_role_demotion_with_overlapping_reservations
        BEFORE UPDATE OF role ON users
        FOR EACH ROW
        WHEN OLD.role IN ('librarian', 'admin')
         AND COALESCE(NEW.role, '') NOT IN ('librarian', 'admin')
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations r1
                    JOIN reservations r2 ON r1.user_id = r2.user_id AND r1.id < r2.id
                    WHERE r1.user_id = NEW.id
                      AND r1.status = 'active'
                      AND r2.status = 'active'
                      AND r1.start_time < r2.end_time
                      AND r1.end_time > r2.start_time
                )
                THEN RAISE(ABORT, 'Role update rejected: user holds overlapping active reservations that violate student/teacher policy.')
            END;
        END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_role_demotion_with_overlapping_reservations")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_user_reservation_overlap_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_user_reservation_overlap_insert")

    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reservations_checked_in_at'))
        batch_op.drop_column('actual_attendees')
        batch_op.drop_column('expected_attendees')
        batch_op.drop_column('checked_in_at')

    # Re-ensure the 4 resource collision triggers after downgrade table recreation
    if bind and bind.dialect.name == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_update")

        op.execute("""
        CREATE TRIGGER trg_prevent_seat_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_seat_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE seat_id = NEW.seat_id
                      AND id != NEW.id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_room_reservation_insert
        BEFORE INSERT ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)

        op.execute("""
        CREATE TRIGGER trg_prevent_room_reservation_update
        BEFORE UPDATE ON reservations
        FOR EACH ROW
        WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
        BEGIN
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 FROM reservations
                    WHERE room_id = NEW.room_id
                      AND id != NEW.id
                      AND status = 'active'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                )
                THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
            END;
        END;
        """)

