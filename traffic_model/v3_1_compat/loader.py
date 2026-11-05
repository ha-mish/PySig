from pathlib import Path
from .domain import (
    Lane,
    Movement,
    Phase,
    Controller,
    Route,
    AssignmentSettings,
    OptimisationSettings,
    Model,
    Conflict,
)


def load_model(path):
    import yaml

    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    s = d.get("settings", {})
    pcu = float(s.get("pcu_length_m", 7.35))
    lanes = {
        x["id"]: Lane(
            x["id"],
            float(x.get("storage_pcu", float(x.get("physical_length_m", 73.5)) / pcu)),
            dict(x["saturation_flow"]),
            x.get("parent_lane_id"),
        )
        for x in d["lanes"]
    }
    moves = {
        x["id"]: Movement(
            x["id"],
            x["from_lane_id"],
            x["signal_group_id"],
            float(x.get("free_flow_time_s", 0)),
        )
        for x in d["movements"]
    }
    conflicts = tuple(
        Conflict(
            x["yielding_movement_id"],
            tuple(x.get("gives_way_to", [])),
            float(x.get("active_capacity_factor", 1)),
        )
        for x in d.get("movement_conflicts", [])
    )
    phases = tuple(
        Phase(
            x["id"],
            tuple(x["active_signal_groups"]),
            float(x["duration_s"]),
            float(x.get("intergreen_after_s", 0)),
        )
        for x in d["phases"]
    )
    c = d["controller"]
    ctl = Controller(
        c["id"], float(c["cycle_time_s"]), float(c.get("offset_s", 0)), phases
    )
    routes = {
        x["id"]: Route(
            x["id"],
            x["origin_zone_id"],
            x["destination_zone_id"],
            tuple(x["movement_ids"]),
        )
        for x in d["routes"]
    }
    od = {
        (o, z): float(v)
        for o, row in d["origin_destination_matrix"]["values"].items()
        for z, v in row.items()
    }
    a = d.get("assignment", {})
    aset = AssignmentSettings(
        int(a.get("max_iterations", 30)),
        float(a.get("relative_gap_tolerance", 0.01)),
        float(a.get("max_flow_change_tolerance", 1)),
        float(a.get("conservation_tolerance", 1e-6)),
    )
    o = d.get("optimisation", {})
    oset = OptimisationSettings(
        str(o.get("objective", "delay")),
        tuple(map(float, o.get("cycle_times_s", [ctl.cycle_time_s]))),
        float(o.get("split_step_s", 5)),
        float(o.get("offset_step_s", 5)),
        float(o.get("minimum_phase_green_s", 10)),
        int(o.get("maximum_candidates", 1000)),
        float(o.get("queue_storage_utilisation_limit", 1)),
        int(o.get("outer_iterations", 3)),
        float(o.get("outer_flow_tolerance", 1)),
        float(o.get("prc_target_dos", 0.9)),
        str(o.get("unconverged_candidate_policy", "reject")),
    )
    sim = d.get("simulation", {})
    return Model(
        d["model"]["id"],
        lanes,
        moves,
        conflicts,
        ctl,
        routes,
        od,
        aset,
        oset,
        pcu,
        float(s.get("lane_start_displacement_s", 3)),
        float(s.get("lane_end_displacement_s", 3)),
        int(sim.get("reporting_cycles", 10)),
        int(sim.get("warm_up_cycles", 3)),
    )
