"""Expected-value front-blocking model for WA shared-lane arrow operation.

This is a planning-level analytical approximation. It represents a single-file
shared lane where movements with red signal groups may reach the queue front
and block movements that have green. Vehicle destinations are assumed to be
independently mixed according to the current movement queue proportions.
"""

from dataclasses import dataclass
from math import inf


@dataclass(frozen=True, slots=True)
class FrontBlockingState:
    eligible_proportion: float
    blocked_proportion: float
    expected_discharge_before_blocking_pcu: float
    service_duration_before_blocking_s: float
    blocking_applies: bool


def movement_proportions(movement_queues, fallback_demands):
    """Return movement proportions from queues, falling back to demand shares."""

    queue_total = sum(max(0.0, value) for value in movement_queues.values())
    source = movement_queues if queue_total > 1e-12 else fallback_demands
    total = sum(max(0.0, value) for value in source.values())
    if total <= 0:
        count = len(source)
        return {key: (1.0 / count if count else 0.0) for key in source}
    return {key: max(0.0, value) / total for key, value in source.items()}


def expected_discharge_before_blocking(eligible_proportion, blocked_proportion):
    """Expected eligible vehicles before the first blocked vehicle.

    Under independent random ordering, N follows a geometric distribution and
    E[N] = p_eligible / p_blocked. A zero blocked proportion gives no blocker.
    """

    if blocked_proportion <= 1e-12:
        return inf
    if eligible_proportion <= 1e-12:
        return 0.0
    return eligible_proportion / blocked_proportion


def front_blocking_state(
    movement_queues,
    fallback_demands,
    eligible_movement_ids,
    lane_service_rate_pcu_per_s,
    interval_duration_s,
):
    """Calculate the expected service window before a red movement blocks."""

    proportions = movement_proportions(movement_queues, fallback_demands)
    eligible = sum(
        proportions.get(movement_id, 0.0) for movement_id in eligible_movement_ids
    )
    eligible = min(1.0, max(0.0, eligible))
    blocked = 1.0 - eligible
    expected = expected_discharge_before_blocking(eligible, blocked)

    if expected == inf or lane_service_rate_pcu_per_s <= 0:
        duration = interval_duration_s
        applies = False
    else:
        duration = min(
            interval_duration_s,
            expected / lane_service_rate_pcu_per_s,
        )
        applies = duration < interval_duration_s - 1e-12

    return FrontBlockingState(
        eligible_proportion=eligible,
        blocked_proportion=blocked,
        expected_discharge_before_blocking_pcu=expected,
        service_duration_before_blocking_s=duration,
        blocking_applies=applies,
    )
