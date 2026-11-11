from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    fixed_time_signals: bool = True
    phase_sequences: bool = True
    phase_overlaps: bool = True
    priority_movements: bool = True
    shared_lane_interactions: bool = False
    finite_link_storage: bool = False
    upstream_spillback: bool = False
