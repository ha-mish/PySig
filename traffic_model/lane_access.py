"""Nested short-lane access trees and cycle-average accessible capacities.

Lane ``physical_length_m`` is the actual lane length measured from lane start to
the stop line. Each lane therefore has its own physical storage. A child lane
must be shorter than its parent and must belong to the same arm/intersection.

The initial Phase 1 capacity formulation is intentionally transparent:
- the root full-length lane provides the sustainable common upstream capacity;
- every non-root short lane can add, per cycle, no more than the vehicles that
  fit in that lane and no more than its own stop-line nominal capacity;
- the resulting tree capacity is allocated across lane demands using an
  equal-degree-of-saturation water-filling method, subject to individual lane
  stop-line capacities.

This creates a parent-lane impact without changing physical base saturation
flows. It is a planning-level analytical formulation, not a reproduction of a
proprietary short-lane model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class LaneAccessNode:
    lane_id: str
    parent_lane_id: str | None
    child_lane_ids: tuple[str, ...]
    depth: int
    physical_length_m: float
    storage_pcu: float


@dataclass(frozen=True, slots=True)
class LaneAccessTree:
    root_lane_id: str
    nodes: dict[str, LaneAccessNode]
    maximum_depth: int


@dataclass(frozen=True, slots=True)
class LaneAccessResult:
    root_lane_id: str
    lane_ids: tuple[str, ...]
    common_upstream_capacity_pcu_per_hour: float
    short_lane_storage_boost_pcu_per_hour: dict[str, float]
    tree_accessible_capacity_pcu_per_hour: float
    lane_accessible_capacity_pcu_per_hour: dict[str, float]
    lane_degree_of_saturation: dict[str, float]
    lane_storage_pcu: dict[str, float]

    def audit(self) -> dict[str, Any]:
        return asdict(self)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _lane_id(lane: Any) -> str:
    return str(_field(lane, "lane_id", _field(lane, "id", "")))


def _parent_id(lane: Any) -> str | None:
    value = _field(lane, "parent_lane_id")
    return str(value) if value not in (None, "") else None


def _length(lane: Any) -> float:
    return float(_field(lane, "physical_length_m", 0.0))


def lane_storage_pcu(lane: Any, pcu_length_m: float) -> float:
    if pcu_length_m <= 0.0:
        raise ValueError("pcu_length_m must be greater than zero")
    return max(0.0, _length(lane) / pcu_length_m)


def validate_lane_access_hierarchy(lanes: Mapping[str, Any]) -> None:
    """Validate parent references, cycles, arm consistency and nesting length."""

    for lane_id, lane in lanes.items():
        parent_id = _parent_id(lane)
        if parent_id is not None and parent_id not in lanes:
            raise ValueError(f"Lane {lane_id} references missing parent {parent_id}")

    # Detect graph cycles before checking geometry so a cyclic hierarchy is
    # reported as such instead of surfacing a secondary length error first.
    for start_id in lanes:
        visited = set()
        current = start_id
        while current is not None:
            if current in visited:
                raise ValueError(f"Lane parent cycle detected from {start_id}")
            visited.add(current)
            current = _parent_id(lanes[current]) if current in lanes else None

    for lane_id, lane in lanes.items():
        parent_id = _parent_id(lane)
        if parent_id is None:
            continue
        parent = lanes[parent_id]
        if _field(lane, "intersection_id") != _field(parent, "intersection_id"):
            raise ValueError(
                f"Lane {lane_id} and parent {parent_id} must share an intersection"
            )
        if _field(lane, "arm_id") != _field(parent, "arm_id"):
            raise ValueError(f"Lane {lane_id} and parent {parent_id} must share an arm")
        if _length(lane) >= _length(parent):
            raise ValueError(
                f"Short lane {lane_id} length must be less than parent {parent_id}"
            )


def build_lane_access_trees(
    lanes: Mapping[str, Any], pcu_length_m: float
) -> tuple[LaneAccessTree, ...]:
    validate_lane_access_hierarchy(lanes)
    children: dict[str, list[str]] = {lane_id: [] for lane_id in lanes}
    roots = []
    for lane_id, lane in lanes.items():
        parent_id = _parent_id(lane)
        if parent_id is None:
            roots.append(lane_id)
        else:
            children[parent_id].append(lane_id)

    trees = []
    for root_id in roots:
        nodes: dict[str, LaneAccessNode] = {}

        def visit(lane_id: str, depth: int) -> None:
            lane = lanes[lane_id]
            child_ids = tuple(sorted(children[lane_id]))
            nodes[lane_id] = LaneAccessNode(
                lane_id=lane_id,
                parent_lane_id=_parent_id(lane),
                child_lane_ids=child_ids,
                depth=depth,
                physical_length_m=_length(lane),
                storage_pcu=lane_storage_pcu(lane, pcu_length_m),
            )
            for child_id in child_ids:
                visit(child_id, depth + 1)

        visit(root_id, 0)
        trees.append(
            LaneAccessTree(
                root_lane_id=root_id,
                nodes=nodes,
                maximum_depth=max(node.depth for node in nodes.values()),
            )
        )
    return tuple(trees)


def _equal_dos_capacity_allocation(
    demand: Mapping[str, float],
    lane_caps: Mapping[str, float],
    total_cap: float,
) -> dict[str, float]:
    """Allocate capacity such that unsaturated lanes tend toward equal DoS."""

    allocation = {lane_id: 0.0 for lane_id in lane_caps}
    remaining = set(lane_caps)
    remaining_cap = max(0.0, total_cap)

    while remaining and remaining_cap > 1e-12:
        total_demand = sum(max(0.0, demand.get(lane_id, 0.0)) for lane_id in remaining)
        if total_demand <= 1e-12:
            equal = remaining_cap / len(remaining)
            for lane_id in tuple(remaining):
                value = min(lane_caps[lane_id], equal)
                allocation[lane_id] += value
                remaining_cap -= value
                remaining.remove(lane_id)
            break

        constrained = []
        for lane_id in remaining:
            share = remaining_cap * max(0.0, demand.get(lane_id, 0.0)) / total_demand
            if share >= lane_caps[lane_id] - allocation[lane_id] - 1e-12:
                constrained.append(lane_id)
        if not constrained:
            for lane_id in remaining:
                allocation[lane_id] += (
                    remaining_cap
                    * max(0.0, demand.get(lane_id, 0.0))
                    / total_demand
                )
            remaining_cap = 0.0
            break
        for lane_id in constrained:
            available = lane_caps[lane_id] - allocation[lane_id]
            allocation[lane_id] += available
            remaining_cap -= available
            remaining.remove(lane_id)

    return allocation


def solve_lane_access_tree(
    tree: LaneAccessTree,
    lane_demands_pcu_per_hour: Mapping[str, float],
    lane_nominal_capacities_pcu_per_hour: Mapping[str, float],
    cycle_time_s: float,
) -> LaneAccessResult:
    if cycle_time_s <= 0.0:
        raise ValueError("cycle_time_s must be greater than zero")

    root_capacity = max(
        0.0, lane_nominal_capacities_pcu_per_hour.get(tree.root_lane_id, 0.0)
    )
    storage_boost = {}
    for lane_id, node in tree.nodes.items():
        if lane_id == tree.root_lane_id:
            continue
        storage_equivalent = node.storage_pcu * 3600.0 / cycle_time_s
        storage_boost[lane_id] = min(
            max(0.0, lane_nominal_capacities_pcu_per_hour.get(lane_id, 0.0)),
            storage_equivalent,
        )

    individual_caps = {
        lane_id: max(0.0, lane_nominal_capacities_pcu_per_hour.get(lane_id, 0.0))
        for lane_id in tree.nodes
    }
    total_cap = min(
        sum(individual_caps.values()), root_capacity + sum(storage_boost.values())
    )
    allocation = _equal_dos_capacity_allocation(
        lane_demands_pcu_per_hour, individual_caps, total_cap
    )
    degree = {
        lane_id: (
            max(0.0, lane_demands_pcu_per_hour.get(lane_id, 0.0)) / capacity
            if capacity > 0.0
            else (
                999.0
                if max(0.0, lane_demands_pcu_per_hour.get(lane_id, 0.0)) > 0.0
                else 0.0
            )
        )
        for lane_id, capacity in allocation.items()
    }
    return LaneAccessResult(
        root_lane_id=tree.root_lane_id,
        lane_ids=tuple(tree.nodes),
        common_upstream_capacity_pcu_per_hour=root_capacity,
        short_lane_storage_boost_pcu_per_hour=storage_boost,
        tree_accessible_capacity_pcu_per_hour=total_cap,
        lane_accessible_capacity_pcu_per_hour=allocation,
        lane_degree_of_saturation=degree,
        lane_storage_pcu={
            lane_id: node.storage_pcu for lane_id, node in tree.nodes.items()
        },
    )


def solve_all_lane_access_trees(
    trees: tuple[LaneAccessTree, ...],
    lane_demands_pcu_per_hour: Mapping[str, float],
    lane_nominal_capacities_pcu_per_hour: Mapping[str, float],
    cycle_time_s: float,
) -> dict[str, LaneAccessResult]:
    return {
        tree.root_lane_id: solve_lane_access_tree(
            tree,
            lane_demands_pcu_per_hour,
            lane_nominal_capacities_pcu_per_hour,
            cycle_time_s,
        )
        for tree in trees
    }
