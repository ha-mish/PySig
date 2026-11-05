def saturation_flow(d):
    if d.get("method", "direct") == "direct":
        return float(d["value_pcu_per_hour"])
    if d.get("method") != "rr67_unopposed":
        raise ValueError("Unsupported saturation-flow method")
    v = (
        2080
        - 140 * bool(d.get("is_nearside_lane", False))
        - 42 * max(0, float(d.get("gradient_percent", 0)))
        + 100 * (float(d.get("lane_width_m", 3.2)) - 3.2)
    )
    f = float(d.get("turning_proportion", 0))
    r = float(d.get("turning_radius_m", 1))
    return max(0, v / (1 + 1.5 * f / r) * float(d.get("local_factor", 1)))
