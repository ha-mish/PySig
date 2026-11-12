"""Assignment-responsive RR67 saturation-flow inputs.

This module derives the turning proportion of each lane from assigned movement
flows. It deliberately leaves the established RR67 equation in ``rr67.py`` and
only prepares its lane-level inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

TURNING_TYPES = {"left", "right", "u_turn", "uturn"}


@dataclass(frozen=True, slots=True)
class DynamicRR67Result:
    lane_id: str
    total_flow_pcu_per_hour: float
    turning_flow_pcu_per_hour: float
    turning_proportion: float
    turning_radius_m: float | None
    turning_proportion_source: str
    turning_radius_source: str
    saturation_flow_pcu_per_hour: float
    rr67_definition: dict[str, Any]

    def audit(self) -> dict[str, Any]:
        return asdict(self)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _lane_id(lane: Any) -> str:
    return str(_field(lane, "lane_id", _field(lane, "id", "")))


def _saturation_definition(lane: Any) -> dict[str, Any]:
    value = _field(lane, "saturation_flow", {})
    return dict(value or {})


def lane_movement_ids(lane: Any, movements: Mapping[str, Any]) -> tuple[str, ...]:
    lane_id = _lane_id(lane)
    return tuple(
        movement_id
        for movement_id, movement in movements.items()
        if _field(movement, "from_lane_id") == lane_id
    )


def assigned_turning_proportion(
    lane: Any,
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
) -> tuple[float, float, float]:
    """Return total flow, turning flow and turning proportion for one lane."""

    total = 0.0
    turning = 0.0
    for movement_id in lane_movement_ids(lane, movements):
        flow = max(0.0, float(movement_flows.get(movement_id, 0.0)))
        total += flow
        movement_type = str(_field(movements[movement_id], "movement_type", "")).lower()
        if movement_type in TURNING_TYPES:
            turning += flow
    proportion = turning / total if total > 0.0 else 0.0
    return total, turning, proportion


def assigned_turning_radius(
    lane: Any,
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
) -> tuple[float | None, str]:
    """Return a turning-flow-weighted radius when movement radii are supplied.

    Movement-level ``turning_radius_m`` is optional. The lane-level RR67 radius
    remains the fallback and is normally sufficient for one turning path.
    """

    weighted_sum = 0.0
    weighted_flow = 0.0
    for movement_id in lane_movement_ids(lane, movements):
        movement = movements[movement_id]
        movement_type = str(_field(movement, "movement_type", "")).lower()
        if movement_type not in TURNING_TYPES:
            continue
        radius = _field(movement, "turning_radius_m")
        flow = max(0.0, float(movement_flows.get(movement_id, 0.0)))
        if radius is not None and float(radius) > 0.0 and flow > 0.0:
            weighted_sum += float(radius) * flow
            weighted_flow += flow
    if weighted_flow > 0.0:
        return weighted_sum / weighted_flow, "assigned_movement_weighted"

    definition = _saturation_definition(lane)
    radius = definition.get("turning_radius_m")
    if radius is not None:
        return float(radius), "lane_input"
    return None, "not_available"


def dynamic_rr67_result(
    lane: Any,
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
    saturation_function=None,
) -> DynamicRR67Result:
    """Calculate assignment-responsive RR67 saturation flow for one lane.

    Backward compatibility:
    - ``turning_proportion_override`` is always treated as a fixed override.
    - A historical ``turning_proportion`` field is also treated as a fixed
      override. Omit both fields to derive the proportion from assignment.
    """

    definition = _saturation_definition(lane)
    method = str(definition.get("method", "direct"))
    total, turning, assigned = assigned_turning_proportion(
        lane, movements, movement_flows
    )

    if "turning_proportion_override" in definition:
        proportion = float(definition["turning_proportion_override"])
        proportion_source = "explicit_override"
    elif "turning_proportion" in definition:
        proportion = float(definition["turning_proportion"])
        proportion_source = "legacy_fixed_input"
    else:
        proportion = assigned
        proportion_source = "assigned_movement_flows"

    if not 0.0 <= proportion <= 1.0:
        raise ValueError(
            f"Lane {_lane_id(lane)} turning proportion must be between 0 and 1"
        )

    radius, radius_source = assigned_turning_radius(
        lane, movements, movement_flows
    )
    effective_definition = dict(definition)
    if method == "rr67_unopposed":
        effective_definition["turning_proportion"] = proportion
        if radius is not None:
            effective_definition["turning_radius_m"] = radius
        elif proportion > 0.0:
            raise ValueError(
                f"Lane {_lane_id(lane)} has assigned turning flow but no "
                "turning_radius_m"
            )

    if saturation_function is None:
        from .rr67 import saturation_flow as saturation_function
    value = float(saturation_function(effective_definition))
    return DynamicRR67Result(
        lane_id=_lane_id(lane),
        total_flow_pcu_per_hour=total,
        turning_flow_pcu_per_hour=turning,
        turning_proportion=proportion,
        turning_radius_m=radius,
        turning_proportion_source=proportion_source,
        turning_radius_source=radius_source,
        saturation_flow_pcu_per_hour=value,
        rr67_definition=effective_definition,
    )


def dynamic_lane_saturation_flows(
    lanes: Mapping[str, Any],
    movements: Mapping[str, Any],
    movement_flows: Mapping[str, float],
    saturation_function=None,
) -> dict[str, DynamicRR67Result]:
    return {
        lane_id: dynamic_rr67_result(
            lane,
            movements,
            movement_flows,
            saturation_function=saturation_function,
        )
        for lane_id, lane in lanes.items()
    }
