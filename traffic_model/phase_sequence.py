"""Phase-sequence and signal-group overlap utilities."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalRun:
    signal_group_id: str
    start_s: float
    end_s: float
    phase_ids: tuple[str, ...]
    ending_intergreen_s: float


def signal_runs(controller, signal_group_id):
    """Return continuous displayed-green runs within one controller cycle.

    Consecutive phases containing the signal group are merged. Intergreen after
    an internal phase boundary is not inserted for that continuing group.
    """
    phases = controller.phases
    if not phases:
        return ()
    starts = []
    cursor = 0.0
    for phase in phases:
        starts.append(cursor)
        cursor += phase.duration_s + phase.intergreen_after_s
    active = [signal_group_id in p.active_signal_groups for p in phases]
    runs = []
    i = 0
    while i < len(phases):
        if not active[i]:
            i += 1
            continue
        start = starts[i]
        ids = [phases[i].phase_id]
        j = i
        while j + 1 < len(phases) and active[j + 1]:
            j += 1
            ids.append(phases[j].phase_id)
        # Continuing signal groups bridge the phase boundary and its nominal
        # phase intergreen. The run ends at the end of the last active phase.
        end = starts[j] + phases[j].duration_s
        runs.append(
            SignalRun(
                signal_group_id,
                start,
                end,
                tuple(ids),
                phases[j].intergreen_after_s,
            )
        )
        i = j + 1
    # Merge cycle-wrapping continuity.
    if len(runs) > 1 and active[0] and active[-1]:
        first, last = runs[0], runs[-1]
        merged = SignalRun(
            signal_group_id,
            last.start_s,
            first.end_s + controller.cycle_time_s,
            last.phase_ids + first.phase_ids,
            first.ending_intergreen_s,
        )
        runs = [merged, *runs[1:-1]]
    return tuple(runs)
