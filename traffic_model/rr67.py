def saturation_flow(defn):
    method = defn.get("method", "direct")
    if method == "direct":
        return float(defn["value_pcu_per_hour"])
    if method != "rr67_unopposed":
        raise ValueError(f"Unsupported saturation-flow method: {method}")
    v = (
        2080
        - 140 * bool(defn.get("is_nearside_lane", False))
        - 42 * max(0, float(defn.get("gradient_percent", 0)))
        + 100 * (float(defn.get("lane_width_m", 3.2)) - 3.2)
    )
    f = float(defn.get("turning_proportion", 0))
    r = float(defn.get("turning_radius_m", 1))
    return max(0, v / (1 + 1.5 * f / r) * float(defn.get("local_factor", 1)))


def capacity_method(defn):
    return str(defn.get("method", "direct"))
