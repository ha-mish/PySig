"""Core PySig domain objects with explicit intersection arms."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Arm:
    arm_id: str
    intersection_id: str
    name: str
    direction: str
    relation: str
    bearing_degrees: float | None = None


@dataclass(frozen=True, slots=True)
class Lane:
    lane_id: str
    intersection_id: str
    storage_pcu: float
    saturation_flow: dict[str, Any]
    parent_lane_id: str | None = None
    physical_length_m: float = 0.0
    arm_id: str | None = None


@dataclass(frozen=True, slots=True)
class Movement:
    movement_id: str
    intersection_id: str
    from_lane_id: str
    to_lane_id: str | None
    signal_group_id: str
    free_flow_time_s: float = 0.0
    movement_type: str = "unknown"


@dataclass(frozen=True, slots=True)
class Phase:
    phase_id: str
    controller_id: str
    active_signal_groups: tuple[str, ...]
    duration_s: float
    intergreen_after_s: float = 0.0


@dataclass(frozen=True, slots=True)
class Controller:
    controller_id: str
    intersection_id: str
    cycle_time_s: float
    offset_s: float
    phases: tuple[Phase, ...]
    optimisation_enabled: bool = True
    cycle_candidates: tuple[float, ...] = ()
    split_step_s: float = 5.0
    offset_step_s: float = 5.0
    minimum_green_s: float = 10.0


@dataclass(frozen=True, slots=True)
class PhaseSequence:
    sequence_id: str
    controller_id: str
    phase_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MovementConflict:
    yielding_movement_id: str
    priority_movement_ids: tuple[str, ...]
    active_capacity_factor: float = 1.0
    conflict_type: str = "opposing_traffic"


@dataclass(frozen=True, slots=True)
class Intersection:
    intersection_id: str
    controller_id: str
    movement_ids: tuple[str, ...]
    arm_ids: tuple[str, ...] = ()
    name: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkLink:
    link_id: str
    from_intersection_id: str
    to_intersection_id: str
    upstream_movement_id: str
    downstream_movement_id: str
    length_m: float
    speed_kmh: float
    storage_pcu: float
    dispersion: float = 0.0


@dataclass(frozen=True, slots=True)
class Route:
    route_id: str
    origin_zone_id: str
    destination_zone_id: str
    movement_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentSettings:
    max_iterations: int = 30
    max_flow_change_tolerance: float = 1.0
    conservation_tolerance: float = 1e-6
    theta: float = 0.08


@dataclass(frozen=True, slots=True)
class NetworkSettings:
    horizon_s: float = 3600.0
    time_slice_s: float = 5.0
    warm_up_s: float = 0.0


@dataclass(frozen=True, slots=True)
class OptimisationSettings:
    mode: str = "optimise_network"
    method: str = "sequential"
    objective: str = "network_delay"
    outer_iterations: int = 3
    outer_flow_tolerance: float = 1.0
    max_candidates_per_controller: int = 100
    max_lane_storage_utilisation: float = 0.95
    max_link_storage_utilisation: float = 0.95
    common_cycle: bool = False
    common_cycle_candidates: tuple[float, ...] = ()
    unconverged_candidate_policy: str = "reject"


@dataclass(frozen=True, slots=True)
class Model:
    model_id: str
    model_name: str
    lanes: dict
    movements: dict
    intersections: dict
    controllers: dict
    links: dict
    routes: dict
    od: dict
    assignment: AssignmentSettings
    network: NetworkSettings
    optimisation: OptimisationSettings
    pcu_length_m: float = 7.35
    start_displacement_s: float = 3.0
    end_displacement_s: float = 3.0
    calculation_method: str = "simulation"
    phase_sequences: dict | None = None
    conflicts: tuple = ()
    los_standard: str = "hcm_signalized"
    los_basis: str = "queueing_delay_seconds_per_pcu"
    arms: dict | None = None
