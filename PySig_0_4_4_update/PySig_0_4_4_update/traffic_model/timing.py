"""Signal timing definitions used by PySig 0.4.4."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GreenTime:
    """Auditable signal and effective-green values for one signal group."""

    cycle_time_s: float
    signal_green_s: float
    start_displacement_s: float
    end_displacement_s: float
    effective_green_s: float
    effective_green_ratio: float


def signal_green_seconds(controller, signal_group_id: str) -> float:
    """Return displayed/active green, excluding every intergreen."""

    return sum(
        phase.duration_s
        for phase in controller.phases
        if signal_group_id in phase.active_signal_groups
    )


def effective_green_seconds(
    signal_green_s: float,
    cycle_time_s: float,
    start_displacement_s: float,
    end_displacement_s: float,
) -> float:
    """Return engineering effective green.

    PySig defines start displacement as service lost after displayed green starts,
    and end displacement as effective service gained after displayed green ends.

        effective green = signal green - start displacement + end displacement

    The result is bounded to the interval [0, cycle time].
    """

    value = signal_green_s - start_displacement_s + end_displacement_s
    return min(cycle_time_s, max(0.0, value))


def green_time(
    controller,
    signal_group_id: str,
    start_displacement_s: float,
    end_displacement_s: float,
) -> GreenTime:
    """Build all green-time quantities for one controller signal group."""

    signal_green_s = signal_green_seconds(controller, signal_group_id)
    effective_green_s = effective_green_seconds(
        signal_green_s=signal_green_s,
        cycle_time_s=controller.cycle_time_s,
        start_displacement_s=start_displacement_s,
        end_displacement_s=end_displacement_s,
    )
    ratio = (
        effective_green_s / controller.cycle_time_s
        if controller.cycle_time_s > 0
        else 0.0
    )
    return GreenTime(
        cycle_time_s=controller.cycle_time_s,
        signal_green_s=signal_green_s,
        start_displacement_s=start_displacement_s,
        end_displacement_s=end_displacement_s,
        effective_green_s=effective_green_s,
        effective_green_ratio=ratio,
    )


def nominal_capacity_pcu_per_hour(
    saturation_flow_pcu_per_hour: float,
    effective_green_ratio: float,
) -> float:
    """Return conventional fixed-time capacity, c = s(g/C)."""

    return saturation_flow_pcu_per_hour * effective_green_ratio


def nominal_degree_of_saturation(
    demand_pcu_per_hour: float,
    nominal_capacity: float,
) -> float:
    """Return conventional degree of saturation, x = q/c."""

    if nominal_capacity > 0:
        return demand_pcu_per_hour / nominal_capacity
    return 999.0 if demand_pcu_per_hour > 0 else 0.0
