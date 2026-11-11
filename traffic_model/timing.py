"""Signal timing definitions used by PySig 0.4.5."""
from dataclasses import dataclass
from .phase_sequence import signal_runs


@dataclass(frozen=True, slots=True)
class GreenTime:
    cycle_time_s: float
    signal_green_s: float
    start_displacement_s: float
    end_displacement_s: float
    effective_green_s: float
    effective_green_ratio: float


def signal_green_seconds(controller, signal_group_id):
    return sum(
        run.end_s - run.start_s for run in signal_runs(controller, signal_group_id)
    )


def effective_green_seconds(
    signal_green_s, cycle_time_s, start_displacement_s, end_displacement_s
):
    value = signal_green_s - start_displacement_s + end_displacement_s
    return min(cycle_time_s, max(0.0, value))


def green_time(controller, signal_group_id, start_displacement_s, end_displacement_s):
    signal = signal_green_seconds(controller, signal_group_id)
    effective = effective_green_seconds(
        signal, controller.cycle_time_s, start_displacement_s, end_displacement_s
    )
    ratio = effective / controller.cycle_time_s if controller.cycle_time_s > 0 else 0.0
    return GreenTime(
        controller.cycle_time_s,
        signal,
        start_displacement_s,
        end_displacement_s,
        effective,
        ratio,
    )


def nominal_capacity_pcu_per_hour(saturation_flow_pcu_per_hour, effective_green_ratio):
    return saturation_flow_pcu_per_hour * effective_green_ratio


def nominal_degree_of_saturation(demand_pcu_per_hour, nominal_capacity):
    if nominal_capacity > 0:
        return demand_pcu_per_hour / nominal_capacity
    return 999.0 if demand_pcu_per_hour > 0 else 0.0
