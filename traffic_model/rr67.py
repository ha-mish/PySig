"""Transparent RR67-style unopposed saturation-flow calculation."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True, slots=True)
class RR67Result:
    saturation_flow_pcu_per_hour: float
    lane_width_m: float
    gradient_percent: float
    is_nearside_lane: bool
    turning_proportion: float
    turning_radius_m: float
    local_factor: float
    base_component_pcu_per_hour: float
    turning_divisor: float


def rr67_result(defn):
    width = float(defn.get("lane_width_m", 3.2))
    gradient = float(defn.get("gradient_percent", 0.0))
    nearside = bool(defn.get("is_nearside_lane", False))
    turning = float(defn.get("turning_proportion", 0.0))
    radius = float(defn.get("turning_radius_m", 1.0))
    local = float(defn.get("local_factor", 1.0))
    if width <= 0:
        raise ValueError("lane_width_m must be greater than zero")
    if not 0 <= turning <= 1:
        raise ValueError("turning_proportion must be between 0 and 1")
    if turning > 0 and radius <= 0:
        raise ValueError(
            "turning_radius_m must be positive when turning traffic exists"
        )
    if local <= 0:
        raise ValueError("local_factor must be greater than zero")
    base = 2080 - 140 * nearside - 42 * max(0.0, gradient) + 100 * (width - 3.2)
    divisor = 1 + 1.5 * turning / radius
    value = max(0.0, base / divisor * local)
    return RR67Result(
        value, width, gradient, nearside, turning, radius, local, base, divisor
    )


def saturation_flow(defn):
    method = defn.get("method", "direct")
    if method == "direct":
        return float(defn["value_pcu_per_hour"])
    if method != "rr67_unopposed":
        raise ValueError(f"Unsupported saturation-flow method: {method}")
    return rr67_result(defn).saturation_flow_pcu_per_hour


def calculation_audit(defn):
    if defn.get("method", "direct") == "direct":
        return {"method": "direct", "value_pcu_per_hour": saturation_flow(defn)}
    return {"method": "rr67_unopposed", **asdict(rr67_result(defn))}


def capacity_method(defn):
    return str(defn.get("method", "direct"))
