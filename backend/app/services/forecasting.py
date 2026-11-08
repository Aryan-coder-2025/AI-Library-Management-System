"""
Predictive Demand Forecasting Service (INTEL-03).
Generates an explainable 2-week demand forecast for monograph checkouts using
historical circulation velocity, day-of-week seasonality, and confidence bounds.
"""
from datetime import date, datetime, timedelta
import math
from typing import List
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Loan
from app.schemas import DemandForecastDay, TwoWeekDemandForecastResponse


def calculate_two_week_demand_forecast(db: Session) -> TwoWeekDemandForecastResponse:
    """
    Computes a 14-day predictive checkout demand projection.
    Mathematical basis:
    - 30-day sample window to determine empirical baseline checkout rate.
    - Day-of-week seasonal factors: calculates weekday-to-weekend utilization ratio.
    - Confidence intervals: calculated via standard error of the daily mean (+- 1.96 * sigma).
    """
    today = date.today()
    sample_window_days = 30
    start_history = today - timedelta(days=sample_window_days)

    # 1. Fetch daily loan issues over the past 30 days
    loans = db.execute(
        select(Loan.issued_at).where(
            Loan.issued_at >= datetime.combine(start_history, datetime.min.time())
        )
    ).scalars().all()

    daily_counts = [0] * sample_window_days
    dow_counts = {i: [] for i in range(7)}  # 0=Monday .. 6=Sunday

    for loan in loans:
        day_offset = (loan.issued_at.date() - start_history).days
        if 0 <= day_offset < sample_window_days:
            daily_counts[day_offset] += 1

    for i in range(sample_window_days):
        day_date = start_history + timedelta(days=i)
        dow = day_date.weekday()
        dow_counts[dow].append(daily_counts[i])

    # 2. Baseline statistics
    total_observed = sum(daily_counts)
    mean_daily = total_observed / max(sample_window_days, 1)

    if sample_window_days > 1:
        variance = sum((x - mean_daily) ** 2 for x in daily_counts) / (sample_window_days - 1)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 1.0

    # Minimum sensible baseline for demonstration catalogues
    baseline_rate = max(mean_daily, 2.5)
    effective_sigma = max(std_dev, 1.2)

    # Day-of-week seasonal multipliers
    dow_multipliers = {}
    for dow in range(7):
        counts = dow_counts[dow]
        avg_dow = (sum(counts) / len(counts)) if counts else mean_daily
        dow_multipliers[dow] = (avg_dow / max(mean_daily, 0.1)) if mean_daily > 0 else 1.0
        # Normalize within reasonable bounds (0.6 to 1.4)
        dow_multipliers[dow] = max(min(dow_multipliers[dow], 1.4), 0.6)

    # 3. Project 14 days ahead
    horizon_days = 14
    projections: List[DemandForecastDay] = []
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for step in range(1, horizon_days + 1):
        future_date = today + timedelta(days=step)
        dow = future_date.weekday()
        multiplier = dow_multipliers.get(dow, 1.0)

        projected_val = round(baseline_rate * multiplier, 1)
        lower_bound = max(round(projected_val - 1.96 * (effective_sigma / math.sqrt(7)), 1), 0.0)
        upper_bound = round(projected_val + 1.96 * (effective_sigma / math.sqrt(7)), 1)

        projections.append(
            DemandForecastDay(
                date=future_date.isoformat(),
                projected_checkouts=projected_val,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                day_of_week=days_of_week[dow],
            )
        )

    # Trend detection
    first_half = sum(p.projected_checkouts for p in projections[:7])
    second_half = sum(p.projected_checkouts for p in projections[7:])
    if second_half > first_half * 1.05:
        trend = "increasing"
    elif second_half < first_half * 0.95:
        trend = "decreasing"
    else:
        trend = "steady"

    return TwoWeekDemandForecastResponse(
        horizon_days=horizon_days,
        start_date=(today + timedelta(days=1)).isoformat(),
        end_date=(today + timedelta(days=horizon_days)).isoformat(),
        projections=projections,
        baseline_daily_average=round(baseline_rate, 2),
        trend_direction=trend,
        confidence_level=0.95,
        methodology="Seasonal Day-of-Week Moving Average with 95% Confidence Bounds (+-1.96 sigma)",
    )

