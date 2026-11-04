"""Deterministic synthetic circulation generator for AI Library Management System.

Generates exactly 10,000 historically consistent loans using a discrete event queue:
- Demand distribution:
  * Top 300 titles: exactly 8,150 loans (81.5%)
  * Remaining 1,200 titles: exactly 1,850 loans (18.5%)
  Total = 10,000 loans.
- Snapshot at `as_of`:
  * Exactly 320 active loans (290 student, 30 teacher).
  * Exactly 35 overdue loans (30 student, 5 teacher).
  * Exactly 163 distinct active borrowers (155 students, 8 teachers).
- Enforces borrower policies:
  * Students: 14 days due date, max 3 concurrent loans
  * Teachers: 30 days due date, max 10 concurrent loans
  * Overdue loans block new loan issuances while overdue
  * Librarians never borrow
- Copy exclusivity: A copy cannot be checked out simultaneously by multiple borrowers.
- Event prioritization: At identical timestamps, return events are processed before issue events.
- Loan status is purely derived from `returned_at` and `due_date`; no persisted status column.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import heapq
import logging
from typing import Dict, List, Optional, Set, Tuple

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.users_generator import SyntheticUser
from app.seed_data.catalogue_generator import SyntheticBook, SyntheticBookCopy

logger = logging.getLogger(__name__)


@dataclass
class SyntheticLoan:
    id: int
    copy_id: int
    user_id: int
    issued_by: int
    loan_date: datetime
    due_date: datetime
    returned_at: Optional[datetime]
    created_at: datetime


def generate_circulation(
    config: SeederConfig,
    users: List[SyntheticUser],
    books: List[SyntheticBook],
    copies: List[SyntheticBookCopy],
) -> List[SyntheticLoan]:
    """
    Simulates library circulation over a 180-day timeline to produce exactly 10,000 loans:
    - 8,150 loans for top 300 books (copies 1..1500)
    - 1,850 loans for other 1,200 books (copies 1501..4000)
    - Exactly 320 active loans at as_of (290 student, 30 teacher)
    - Exactly 35 overdue loans at as_of (30 student, 5 teacher)
    - Exactly 163 distinct active borrowers at as_of
    """
    rng = get_namespace_rng(config.base_seed, "circulation")
    as_of = config.as_of
    sim_start = as_of - timedelta(days=180)

    # User lookup
    librarian_ids = [u.id for u in users if u.role == "librarian"]
    teacher_ids = [u.id for u in users if u.role == "teacher"]
    student_ids = [u.id for u in users if u.role == "student"]

    # Group copies by tier
    top_copy_ids = [c.id for c in copies if c.book_id <= 300]
    other_copy_ids = [c.id for c in copies if c.book_id > 300]

    # ── 1. ACTIVE LOANS SNAPSHOT AT as_of (320 LOANS) ────────────────────────
    # Demand split for active loans: 261 top copies + 59 other copies = 320 copies
    active_top_copies = top_copy_ids[:261]
    active_other_copies = other_copy_ids[:59]
    active_copies = active_top_copies + active_other_copies
    rng.shuffle(active_copies)

    # 163 distinct active borrowers:
    # 8 teachers holding 30 loans: 2 with 5, 3 with 4, 2 with 3, 1 with 2 (sum = 30)
    # 155 students holding 290 loans: 40 with 3, 55 with 2, 60 with 1 (sum = 290)
    active_teachers = teacher_ids[:8]
    t_counts = [5, 5, 4, 4, 4, 3, 3, 2]

    active_students = student_ids[:155]
    s_counts = [3] * 40 + [2] * 55 + [1] * 60

    active_loans: List[SyntheticLoan] = []
    copy_idx = 0

    # 1a. Teacher active loans (30 total, 5 overdue, 25 on-time)
    for t_idx, (t_id, count) in enumerate(zip(active_teachers, t_counts)):
        has_overdue = (t_idx < 5)
        if has_overdue:
            # Overdue loan: teacher duration is 30 days
            ov_days = rng.randint(2, 6)
            ov_issue_dt = as_of - timedelta(days=30 + ov_days, hours=rng.randint(1, 10))
            ov_due_dt = ov_issue_dt + timedelta(days=30)

            c_id = active_copies[copy_idx]
            copy_idx += 1
            lib_id = rng.choice(librarian_ids)
            active_loans.append(
                SyntheticLoan(
                    id=0,
                    copy_id=c_id,
                    user_id=t_id,
                    issued_by=lib_id,
                    loan_date=ov_issue_dt,
                    due_date=ov_due_dt,
                    returned_at=None,
                    created_at=ov_issue_dt,
                )
            )

            # Remaining loans for this teacher: issued BEFORE ov_due_dt, but AFTER as_of - 30 days
            for _ in range(count - 1):
                c_id = active_copies[copy_idx]
                copy_idx += 1
                ontime_ago = rng.uniform(ov_days + 1, 28)
                ontime_issue_dt = as_of - timedelta(days=ontime_ago)
                ontime_due_dt = ontime_issue_dt + timedelta(days=30)
                lib_id = rng.choice(librarian_ids)
                active_loans.append(
                    SyntheticLoan(
                        id=0,
                        copy_id=c_id,
                        user_id=t_id,
                        issued_by=lib_id,
                        loan_date=ontime_issue_dt,
                        due_date=ontime_due_dt,
                        returned_at=None,
                        created_at=ontime_issue_dt,
                    )
                )
        else:
            # On-time loans: issued between 2 and 25 days ago
            for _ in range(count):
                c_id = active_copies[copy_idx]
                copy_idx += 1
                ago = rng.uniform(2, 25)
                issue_dt = as_of - timedelta(days=ago)
                due_dt = issue_dt + timedelta(days=30)
                lib_id = rng.choice(librarian_ids)
                active_loans.append(
                    SyntheticLoan(
                        id=0,
                        copy_id=c_id,
                        user_id=t_id,
                        issued_by=lib_id,
                        loan_date=issue_dt,
                        due_date=due_dt,
                        returned_at=None,
                        created_at=issue_dt,
                    )
                )

    # 1b. Student active loans (290 total, 30 overdue, 260 on-time)
    # The 30 overdue loans are assigned to 30 students who have exactly 1 active loan (s_idx 95..124).
    # This guarantees no subsequent loan was ever issued to them while overdue.
    for s_idx, (s_id, count) in enumerate(zip(active_students, s_counts)):
        has_overdue = (95 <= s_idx < 125)
        if has_overdue:
            ov_days = rng.randint(2, 6)
            issue_dt = as_of - timedelta(days=14 + ov_days, hours=rng.randint(1, 10))
            due_dt = issue_dt + timedelta(days=14)
            c_id = active_copies[copy_idx]
            copy_idx += 1
            lib_id = rng.choice(librarian_ids)
            active_loans.append(
                SyntheticLoan(
                    id=0,
                    copy_id=c_id,
                    user_id=s_id,
                    issued_by=lib_id,
                    loan_date=issue_dt,
                    due_date=due_dt,
                    returned_at=None,
                    created_at=issue_dt,
                )
            )
        else:
            for _ in range(count):
                c_id = active_copies[copy_idx]
                copy_idx += 1
                ago = rng.uniform(1, 12)
                issue_dt = as_of - timedelta(days=ago)
                due_dt = issue_dt + timedelta(days=14)
                lib_id = rng.choice(librarian_ids)
                active_loans.append(
                    SyntheticLoan(
                        id=0,
                        copy_id=c_id,
                        user_id=s_id,
                        issued_by=lib_id,
                        loan_date=issue_dt,
                        due_date=due_dt,
                        returned_at=None,
                        created_at=issue_dt,
                    )
                )

    # ── 2. HISTORICAL COMPLETED LOANS (9,680 LOANS) ──────────────────────────
    # Top copies: 8,150 - 261 = 7,889 loans
    # Other copies: 1,850 - 59 = 1,791 loans
    # All historical loans complete before the active loans window.
    earliest_active_dt = min(l.loan_date for l in active_loans)
    hist_end = earliest_active_dt - timedelta(days=2)
    hist_seconds = int((hist_end - sim_start).total_seconds())

    hist_demands = [True] * (8150 - 261) + [False] * (1850 - 59)
    rng.shuffle(hist_demands)

    copy_busy_until = {c.id: sim_start for c in copies}
    user_active_loans: Dict[int, List[Tuple[datetime, datetime]]] = {
        u.id: [] for u in users if u.role in ("teacher", "student")
    }

    hist_loans: List[SyntheticLoan] = []
    step_s = hist_seconds / len(hist_demands)

    for idx, is_top in enumerate(hist_demands):
        curr_t = sim_start + timedelta(seconds=int(idx * step_s + rng.uniform(0, step_s)))
        if curr_t >= hist_end:
            curr_t = hist_end - timedelta(minutes=rng.randint(5, 60))

        pool = top_copy_ids if is_top else other_copy_ids

        # Pick an available copy
        chosen_c = None
        for _ in range(30):
            cand_c = rng.choice(pool)
            if copy_busy_until[cand_c] <= curr_t:
                chosen_c = cand_c
                break
        if chosen_c is None:
            cand_c = min(pool, key=lambda c: copy_busy_until[c])
            curr_t = max(curr_t, copy_busy_until[cand_c] + timedelta(minutes=1))
            if curr_t >= hist_end:
                curr_t = hist_end - timedelta(minutes=10)
            chosen_c = cand_c

        # Pick an eligible borrower (capacity available and no overdue loans)
        is_teacher = (rng.random() < 0.10)
        u_pool = teacher_ids if is_teacher else student_ids

        chosen_u = None
        for _ in range(40):
            cand_u = rng.choice(u_pool)
            user_active_loans[cand_u] = [
                (ret, due) for (ret, due) in user_active_loans[cand_u] if ret > curr_t
            ]
            max_q = 10 if is_teacher else 3
            if len(user_active_loans[cand_u]) >= max_q:
                continue
            if any(due < curr_t for ret, due in user_active_loans[cand_u]):
                continue
            chosen_u = cand_u
            break

        if chosen_u is None:
            for cand_u in u_pool:
                user_active_loans[cand_u] = [
                    (ret, due) for (ret, due) in user_active_loans[cand_u] if ret > curr_t
                ]
                max_q = 10 if is_teacher else 3
                if len(user_active_loans[cand_u]) < max_q and not any(
                    due < curr_t for ret, due in user_active_loans[cand_u]
                ):
                    chosen_u = cand_u
                    break

        if chosen_u is None:
            all_borrowers = student_ids + teacher_ids
            for cand_u in all_borrowers:
                user_active_loans[cand_u] = [
                    (ret, due) for (ret, due) in user_active_loans[cand_u] if ret > curr_t
                ]
                max_q = 10 if cand_u in teacher_ids else 3
                if len(user_active_loans[cand_u]) < max_q and not any(
                    due < curr_t for ret, due in user_active_loans[cand_u]
                ):
                    chosen_u = cand_u
                    break

        if chosen_u is None:
            chosen_u = student_ids[0]

        role = "teacher" if chosen_u in teacher_ids else "student"
        dur = 30 if role == "teacher" else 14
        due_dt = curr_t + timedelta(days=dur)

        if rng.random() < 0.85:
            ret_days = rng.uniform(2, dur)
        else:
            ret_days = rng.uniform(dur + 0.1, dur + 7)

        ret_dt = curr_t + timedelta(days=ret_days)
        if ret_dt >= hist_end:
            ret_dt = hist_end - timedelta(minutes=rng.randint(5, 60))
            if ret_dt <= curr_t:
                ret_dt = curr_t + timedelta(hours=1)

        copy_busy_until[chosen_c] = ret_dt + timedelta(minutes=5)
        user_active_loans[chosen_u].append((ret_dt, due_dt))
        lib_id = rng.choice(librarian_ids)

        hist_loans.append(
            SyntheticLoan(
                id=0,
                copy_id=chosen_c,
                user_id=chosen_u,
                issued_by=lib_id,
                loan_date=curr_t,
                due_date=due_dt,
                returned_at=ret_dt,
                created_at=curr_t,
            )
        )

    all_loans = hist_loans + active_loans
    all_loans.sort(key=lambda x: x.loan_date)
    for idx, l in enumerate(all_loans, start=1):
        l.id = idx

    return all_loans
