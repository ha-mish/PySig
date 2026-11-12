"""Coordinate assignment-responsive RR67 and nested short-lane capacity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .dynamic_rr67 import DynamicRR67Result, dynamic_lane_saturation_flows
from .lane_access import (
    LaneAccessResult,
    build_lane_access_trees,
    solve_all_lane_access_trees,
)


@dataclass(frozen=True, slots=True)
class DynamicCapacityUpdate:
    rr67_by_lane: dict[str, DynamicRR67Result]
    lane_demand_pcu_per_hour: dict[str, float]
    nominal_capacity_pcu_per_hour: dict[str, float]
    accessible_capacity_pcu_per_hour: dict[str, float]
    lane_access_by_root: dict[str, LaneAccessResult]

    def audit(self) -> dict[str, Any]:
        return {
            "rr67_by_lane": {
                lane_id: result.audit() for lane_id, result in self.rr67_by_lane.items()
            },
            "lane_demand_pcu_per_hour": self.lane_demand_pcu_per_hour,
            "nominal_capacity_pcu_per_hour": self.nominal_capacity_pcu_per_hour,
            "accessible_capacity_pcu_per_hour": (self.accessible_capacity_pcu_per_hour),
            "lane_access_by_root": {
                root_id: result.audit()
                for root_id, result in self.lane_access_by_root.items()
            },
        }


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def lane_demands_from_movements(
    lanes: Mapping[str, Any],
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
) -> dict[str, float]:
    result = {lane_id: 0.0 for lane_id in lanes}
    for movement_id, movement in movements.items():
        lane_id = _field(movement, "from_lane_id")
        if lane_id in result:
            result[lane_id] += max(0.0, float(movement_flows.get(movement_id, 0.0)))
    return result


def update_dynamic_capacities(
    lanes: Mapping[str, Any],
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
    effective_green_ratios: Mapping[str, float],
    cycle_times_s: Mapping[str, float],
    pcu_length_m: float,
    saturation_function=None,
) -> DynamicCapacityUpdate:
    """Calculate base saturation, nominal capacity and lane-access capacity.

    ``effective_green_ratios`` and ``cycle_times_s`` are lane-keyed because
    phase/signal timing remains the responsibility of the existing timing
    module. All lanes in one parent-child tree must use the same cycle time.
    """

    rr67 = dynamic_lane_saturation_flows(
        lanes,
        movements,
        movement_flows,
        saturation_function=saturation_function,
    )
    demand = lane_demands_from_movements(lanes, movements, movement_flows)
    nominal = {
        lane_id: result.saturation_flow_pcu_per_hour
        * max(0.0, min(1.0, float(effective_green_ratios.get(lane_id, 0.0))))
        for lane_id, result in rr67.items()
    }
    accessible = dict(nominal)
    trees = build_lane_access_trees(lanes, pcu_length_m)
    access_results = {}
    for tree in trees:
        if len(tree.nodes) == 1:
            continue
        cycles = {
            float(cycle_times_s[lane_id])
            for lane_id in tree.nodes
            if lane_id in cycle_times_s
        }
        if len(cycles) != 1:
            raise ValueError(
                f"Lane access tree {tree.root_lane_id} must use one cycle time"
            )
        cycle = cycles.pop()
        result = solve_all_lane_access_trees((tree,), demand, nominal, cycle)[
            tree.root_lane_id
        ]
        access_results[tree.root_lane_id] = result
        accessible.update(result.lane_accessible_capacity_pcu_per_hour)

    return DynamicCapacityUpdate(
        rr67_by_lane=rr67,
        lane_demand_pcu_per_hour=demand,
        nominal_capacity_pcu_per_hour=nominal,
        accessible_capacity_pcu_per_hour=accessible,
        lane_access_by_root=access_results,
    )
