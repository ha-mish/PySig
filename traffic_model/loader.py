from pathlib import Path
from .domain import (
    Lane,
    Movement,
    Phase,
    Controller,
    Intersection,
    NetworkLink,
    Route,
    AssignmentSettings,
    NetworkSettings,
    OptimisationSettings,
    Model,
    PhaseSequence,
    MovementConflict,
)


def load_model(path):
    import yaml

    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    s = d.get("settings", {})
    pcu = float(s.get("pcu_length_m", 7.35))
    start_displacement_s = float(s.get("lane_start_displacement_s", 3.0))
    end_displacement_s = float(s.get("lane_end_displacement_s", 3.0))
    ints = d.get("intersections") or [
        {
            "id": "I1",
            "controller_id": (
                d.get("controller") or d.get("controllers", [{"id": "C1"}])[0]
            )["id"],
            "movement_ids": [x["id"] for x in d.get("movements", [])],
        }
    ]
    default = ints[0]["id"]
    lanes = {}
    for x in d.get("lanes", []):
        length = float(x.get("physical_length_m", 73.5))
        lanes[x["id"]] = Lane(
            x["id"],
            x.get("intersection_id", default),
            float(x.get("storage_pcu", length / pcu)),
            dict(x["saturation_flow"]),
            x.get("parent_lane_id"),
            length,
        )
    moves = {
        x["id"]: Movement(
            x["id"],
            x.get("intersection_id", default),
            x["from_lane_id"],
            x.get("to_lane_id"),
            x["signal_group_id"],
            float(x.get("free_flow_time_s", 0)),
            str(x.get("movement_type", "unknown")),
        )
        for x in d.get("movements", [])
    }
    cr = d.get("controllers") or ([d["controller"]] if d.get("controller") else [])
    ph = d.get("phases", [])
    controllers = {}
    for c in cr:
        iid = c.get("intersection_id", default)
        ps = tuple(
            Phase(
                x["id"],
                x.get("controller_id", c["id"]),
                tuple(x.get("active_signal_groups", [])),
                float(x["duration_s"]),
                float(x.get("intergreen_after_s", 0)),
            )
            for x in ph
            if x.get("controller_id", c["id"]) == c["id"]
        )
        o = c.get("optimisation", {})
        controllers[c["id"]] = Controller(
            c["id"],
            iid,
            float(c["cycle_time_s"]),
            float(c.get("offset_s", 0)),
            ps,
            bool(o.get("enabled", True)),
            tuple(map(float, o.get("cycle_times_s", [c["cycle_time_s"]]))),
            float(o.get("split_step_s", 5)),
            float(o.get("offset_step_s", 5)),
            float(o.get("minimum_green_s", 10)),
        )
    intersections = {
        x["id"]: Intersection(
            x["id"],
            x.get("controller_id", next(iter(controllers), "C1")),
            tuple(
                x.get(
                    "movement_ids",
                    [m for m, v in moves.items() if v.intersection_id == x["id"]],
                )
            ),
        )
        for x in ints
    }
    links = {
        x["id"]: NetworkLink(
            x["id"],
            x["from_intersection_id"],
            x["to_intersection_id"],
            x["upstream_movement_id"],
            x["downstream_movement_id"],
            float(x["length_m"]),
            float(x["speed_kmh"]),
            float(x["storage_pcu"]),
            float(x.get("dispersion", 0)),
        )
        for x in d.get("network_links", [])
    }
    routes = {
        x["id"]: Route(
            x["id"],
            x["origin_zone_id"],
            x["destination_zone_id"],
            tuple(x["movement_ids"]),
        )
        for x in d.get("routes", [])
    }
    od = {
        (a, b): float(v)
        for a, row in (d.get("origin_destination_matrix", {}).get("values", {})).items()
        for b, v in row.items()
    }
    a = d.get("assignment", {})
    aset = AssignmentSettings(
        int(a.get("max_iterations", 30)),
        float(a.get("max_flow_change_tolerance", 1)),
        float(a.get("conservation_tolerance", 1e-6)),
        float(a.get("theta", 0.08)),
    )
    n = d.get("network", {})
    nset = NetworkSettings(
        float(n.get("horizon_s", 3600)),
        float(n.get("time_slice_s", 5)),
        float(n.get("warm_up_s", 0)),
    )
    o = d.get("optimisation", {})
    run = d.get("run", {})
    os = OptimisationSettings(
        str(run.get("mode", o.get("mode", "optimise_network"))),
        str(o.get("method", "sequential")),
        str(o.get("objective", "network_delay")),
        int(o.get("outer_iterations", 3)),
        float(o.get("outer_flow_tolerance", 1)),
        int(o.get("max_candidates_per_controller", 100)),
        float(
            o.get(
                "max_lane_storage_utilisation",
                o.get("queue_storage_utilisation_limit", 0.95),
            )
        ),
        float(o.get("max_link_storage_utilisation", 0.95)),
        bool(o.get("common_cycle", False)),
        tuple(map(float, o.get("common_cycle_candidates", []))),
        str(o.get("unconverged_candidate_policy", "reject")),
    )
    calculation_method = str(d.get("calculation", {}).get("method", "simulation"))
    if calculation_method not in {"simulation", "analytical"}:
        raise ValueError("calculation.method must be simulation or analytical")
    sequences = {}
    for row in d.get("phase_sequences", []):
        sequences[row["id"]] = PhaseSequence(
            row["id"], row["controller_id"], tuple(row.get("phase_ids", []))
        )
    for controller_id, controller in controllers.items():
        if not any(x.controller_id == controller_id for x in sequences.values()):
            sid = f"SEQ_{controller_id}"
            sequences[sid] = PhaseSequence(
                sid, controller_id, tuple(x.phase_id for x in controller.phases)
            )
    conflicts = []
    for row in d.get("movement_conflicts", []):
        yielding = row.get("yielding_movement_id", row.get("yeilding_movement_id"))
        if not yielding:
            raise ValueError("movement conflict requires yielding_movement_id")
        priorities = row.get("priority_movement_ids", row.get("gives_way_to", []))
        conflicts.append(
            MovementConflict(
                yielding,
                tuple(priorities),
                float(row.get("active_capacity_factor", 1.0)),
                str(row.get("conflict_type", "opposing_traffic")),
            )
        )
    reporting = d.get("reporting", {}).get("level_of_service", {})
    meta = d.get("model", {})
    return Model(
        str(meta.get("id", Path(path).stem)),
        str(meta.get("name", meta.get("id", Path(path).stem))),
        lanes,
        moves,
        intersections,
        controllers,
        links,
        routes,
        od,
        aset,
        nset,
        os,
        pcu,
        start_displacement_s,
        end_displacement_s,
        calculation_method,
        sequences,
        tuple(conflicts),
        str(reporting.get("standard", "hcm_signalized")),
        str(reporting.get("basis", "queueing_delay_seconds_per_pcu")),
    )
