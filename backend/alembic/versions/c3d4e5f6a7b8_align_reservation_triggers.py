"""align reservation triggers with active status

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-31 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        # Drop legacy Step 2A triggers checking ('active', 'confirmed')
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_update")

        # Recreate triggers strictly checking status = 'active'
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


def downgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        # Drop active-only triggers
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_seat_reservation_update")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_room_reservation_update")

        # Recreate Step 2A triggers checking ('active', 'confirmed')
        op.execute("""
        CREATE TRIGGER trg_prevent_seat_reservation_insert
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
        CREATE TRIGGER trg_prevent_seat_reservation_update
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
        CREATE TRIGGER trg_prevent_room_reservation_insert
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
        CREATE TRIGGER trg_prevent_room_reservation_update
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

