"""
CLI runner for scheduled/cron overdue notification sweeps (CIRC-04).
Can be run via cron / scheduled task:
    python -m app.cli_sweep [--as-of-date YYYY-MM-DD]
"""
import argparse
import sys
from datetime import date
from typing import Optional

from app.database import SessionLocal, atomic_write
from app.services.notifications import sweep_and_generate_overdue_notifications
from app.services.spaces import sweep_study_space_reservations_service


def run_sweep(as_of_date_str: Optional[str] = None, db_session = None):
    eval_date = None
    if as_of_date_str:
        try:
            eval_date = date.fromisoformat(as_of_date_str)
        except ValueError:
            print(f"Error: Invalid date format '{as_of_date_str}'. Expected YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    if db_session is not None:
        return sweep_and_generate_overdue_notifications(db=db_session, as_of_date=eval_date)

    with SessionLocal() as db:
        res = sweep_and_generate_overdue_notifications(db=db, as_of_date=eval_date)
        print(f"Overdue sweep complete. Created {res.new_notifications} new notification(s).")
        return res


def run_space_reservations_sweep(as_of_datetime_str: Optional[str] = None, db_session = None):
    """Executes a study space lifecycle sweep via CLI."""
    from datetime import datetime
    eval_dt = None
    if as_of_datetime_str:
        try:
            eval_dt = datetime.fromisoformat(as_of_datetime_str)
        except ValueError:
            print(f"Error: Invalid datetime format '{as_of_datetime_str}'. Expected ISO format.", file=sys.stderr)
            sys.exit(1)

    if db_session is not None:
        with atomic_write(db_session):
            return sweep_study_space_reservations_service(db=db_session, now_utc=eval_dt)

    with SessionLocal() as db:
        with atomic_write(db):
            res = sweep_study_space_reservations_service(db=db, now_utc=eval_dt)
        print(f"Space reservation sweep complete. {res.no_show_count} marked no-show, {res.completed_count} marked completed.")
        return res


def main():
    parser = argparse.ArgumentParser(
        description="Daily CLI runner to scan overdue library loans and manage study space lifecycles."
    )
    parser.add_argument(
        "--as-of-date",
        help="Evaluation baseline date in ISO format (YYYY-MM-DD). Defaults to today.",
        default=None,
    )
    parser.add_argument(
        "--spaces",
        action="store_true",
        help="Run study space reservation no-show and completion sweep.",
    )
    parser.add_argument(
        "--as-of-datetime",
        help="Evaluation baseline datetime in ISO format for study space sweep.",
        default=None,
    )
    args = parser.parse_args()

    if args.spaces:
        run_space_reservations_sweep(args.as_of_datetime)
    else:
        run_sweep(args.as_of_date)


if __name__ == "__main__":
    main()
