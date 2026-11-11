"""Exact analytical service intervals."""
from ...phase_sequence import signal_runs


def service_intervals(
    controller, signal_group_id, horizon_s, start_displacement_s, end_displacement_s
):
    runs = signal_runs(controller, signal_group_id)
    intervals = []
    cycle = controller.cycle_time_s
    first_cycle = int((-controller.offset_s) // cycle) - 1
    last_cycle = int((horizon_s - controller.offset_s) // cycle) + 1
    for n in range(first_cycle, last_cycle + 1):
        base = controller.offset_s + n * cycle
        for run in runs:
            start = base + run.start_s + start_displacement_s
            end = base + run.end_s + end_displacement_s
            clipped = (max(0.0, start), min(horizon_s, end))
            if clipped[1] > clipped[0]:
                intervals.append(clipped)
    return tuple(sorted(intervals))
