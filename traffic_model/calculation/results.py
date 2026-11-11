"""Common analytical result objects for PySig 0.4.5a."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyticalMovementResult:
    movement_id: str
    intersection_id: str
    lane_id: str
    to_lane_id: str | None
    signal_group_id: str
    movement_type: str
    demand_pcu_per_hour: float
    saturation_flow_pcu_per_hour: float
    cycle_time_s: float
    signal_green_s: float
    start_displacement_s: float
    end_displacement_s: float
    effective_green_s: float
    effective_green_ratio: float
    nominal_capacity_pcu_per_hour: float
    nominal_degree_of_saturation: float
    simulated_service_capacity_pcu_per_hour: float
    simulated_degree_of_saturation: float
    arrivals_pcu: float
    departures_pcu: float
    final_queue_pcu: float
    maximum_queue_pcu: float
    maximum_queue_m: float
    total_delay_pcu_hours: float
    mean_delay_seconds_per_pcu: float
    unserved_demand_pcu: float
    storage_overflow_pcu: float
    storage_full_seconds: float
    capacity_method: str
    shared_lane_model: str
    blocked_seconds: float
    expected_discharge_before_blocking_pcu: float | None


@dataclass(frozen=True, slots=True)
class AnalyticalLaneResult:
    lane_id: str
    intersection_id: str
    movement_ids: tuple[str, ...]
    signal_group_ids: tuple[str, ...]
    demand_pcu_per_hour: float
    saturation_flow_pcu_per_hour: float
    cycle_time_s: float
    signal_green_s: float | None
    start_displacement_s: float
    end_displacement_s: float
    effective_green_s: float | None
    effective_green_ratio: float | None
    nominal_capacity_pcu_per_hour: float | None
    nominal_degree_of_saturation: float | None
    simulated_service_capacity_pcu_per_hour: float
    simulated_degree_of_saturation: float
    arrivals_pcu: float
    departures_pcu: float
    final_queue_pcu: float
    maximum_queue_pcu: float
    maximum_queue_m: float
    total_delay_pcu_hours: float
    mean_delay_seconds_per_pcu: float
    unserved_demand_pcu: float
    storage_pcu: float
    storage_utilisation: float
    storage_overflow_pcu: float
    storage_full_seconds: float
    capacity_method: str
    shared_lane_model: str
    blocked_seconds: float
    capacity_lost_to_blocking_pcu: float


@dataclass(frozen=True, slots=True)
class AnalyticalResult:
    """Common result shape consumed by assignment, optimisation and outputs."""

    movements: dict[str, AnalyticalMovementResult]
    lanes: dict[str, AnalyticalLaneResult]
    links: dict
    network_delay_pcu_hours: float
    maximum_lane_storage_utilisation: float
    maximum_link_storage_utilisation: float
    movement_delay_s: dict[str, float]
    throughput_pcu: float
    calculation_method: str = "analytical"
