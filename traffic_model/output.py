from pathlib import Path
from dataclasses import asdict
import csv
import json


def _csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _controller_dict(controller):
    return {
        "controller_id": controller.controller_id,
        "intersection_id": controller.intersection_id,
        "cycle_time_s": controller.cycle_time_s,
        "offset_s": controller.offset_s,
        "phases": [
            {
                "phase_id": phase.phase_id,
                "duration_s": phase.duration_s,
                "intergreen_after_s": phase.intergreen_after_s,
                "active_signal_groups": list(phase.active_signal_groups),
            }
            for phase in controller.phases
        ],
    }


def rich_result(
    model,
    assignment,
    controllers=None,
    optimisation=None,
    result_type="final_assignment",
):
    cs = controllers or model.controllers
    sim = assignment.simulation
    movements = [asdict(row) for row in sim.movements.values()]
    lanes = [asdict(row) for row in sim.lanes.values()]
    total_demand = sum(model.od.values())
    total_departures = sum(row.departures_pcu for row in sim.lanes.values())
    mean_delay = (
        sim.network_delay_pcu_hours * 3600.0 / total_departures
        if total_departures > 0
        else 0.0
    )
    max_lane_dos = max(
        (row.degree_of_saturation for row in sim.lanes.values()), default=0.0
    )
    max_queue = max((row.maximum_queue_pcu for row in sim.lanes.values()), default=0.0)
    max_queue_m = max((row.maximum_queue_m for row in sim.lanes.values()), default=0.0)

    intersections = []
    for intersection_id, intersection in model.intersections.items():
        controller = cs[intersection.controller_id]
        lane_rows = [
            asdict(row)
            for row in sim.lanes.values()
            if row.intersection_id == intersection_id
        ]
        movement_rows = [
            asdict(sim.movements[mid])
            for mid in intersection.movement_ids
            if mid in sim.movements
        ]
        intersections.append(
            {
                "intersection_id": intersection_id,
                "controller": _controller_dict(controller),
                "lanes": lane_rows,
                "movements": movement_rows,
            }
        )

    data = {
        "schema_version": "4.2.2",
        "model_id": model.model_id,
        "model_name": model.model_name,
        "result_type": result_type,
        "run_mode": model.optimisation.mode,
        "simulation": {
            "horizon_s": model.network.horizon_s,
            "time_slice_s": model.network.time_slice_s,
            "warm_up_s": model.network.warm_up_s,
            "pcu_length_m": model.pcu_length_m,
            "queue_kernel": "shared_lane_fifo_composition",
        },
        "summary": {
            "total_od_demand_pcu_per_hour": total_demand,
            "network_delay_pcu_hours": sim.network_delay_pcu_hours,
            "mean_delay_seconds_per_departed_pcu": mean_delay,
            "maximum_lane_degree_of_saturation": max_lane_dos,
            "maximum_queue_pcu": max_queue,
            "maximum_queue_m": max_queue_m,
            "maximum_lane_storage_utilisation": sim.maximum_lane_storage_utilisation,
            "maximum_link_storage_utilisation": sim.maximum_link_storage_utilisation,
            "assignment_converged": assignment.converged,
            "assignment_iterations": len(assignment.iterations),
            "od_conservation_error": (
                assignment.iterations[-1].conservation_error
                if assignment.iterations
                else 0.0
            ),
        },
        "lanes": lanes,
        "movements": movements,
        "intersections": intersections,
        "links": [asdict(row) for row in sim.links.values()],
        "routes": [
            {
                "route_id": route_id,
                "origin_zone_id": model.routes[route_id].origin_zone_id,
                "destination_zone_id": model.routes[route_id].destination_zone_id,
                "movement_ids": list(model.routes[route_id].movement_ids),
                "assigned_flow_pcu_per_hour": flow,
            }
            for route_id, flow in assignment.route_flows.items()
        ],
        "assignment": {
            "converged": assignment.converged,
            "iterations": [asdict(row) for row in assignment.iterations],
        },
    }
    if optimisation is not None:
        data["optimisation"] = {
            "converged": optimisation.converged,
            "outer_iterations": optimisation.outer_iterations,
            "signal_plans_stable": optimisation.signal_plans_stable,
            "route_flows_stable": optimisation.route_flows_stable,
            "objective": model.optimisation.objective,
            "controllers": {
                key: _controller_dict(value)
                for key, value in optimisation.controllers.items()
            },
        }
    return data


def write_outputs(
    model,
    assignment,
    out,
    controllers=None,
    optimisation=None,
    result_type="final_assignment",
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = rich_result(model, assignment, controllers, optimisation, result_type)
    (out / "results.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    _csv(
        out / "lane_results.csv",
        (asdict(row) for row in assignment.simulation.lanes.values()),
    )
    _csv(
        out / "movement_results.csv",
        (asdict(row) for row in assignment.simulation.movements.values()),
    )
    _csv(
        out / "route_assignment.csv",
        (
            {
                "route_id": route_id,
                "origin_zone_id": model.routes[route_id].origin_zone_id,
                "destination_zone_id": model.routes[route_id].destination_zone_id,
                "assigned_flow_pcu_per_hour": flow,
                "movement_path": " > ".join(model.routes[route_id].movement_ids),
            }
            for route_id, flow in assignment.route_flows.items()
        ),
    )
    _csv(
        out / "network_links.csv",
        (asdict(row) for row in assignment.simulation.links.values()),
    )
    _csv(
        out / "assignment_iterations.csv",
        (asdict(row) for row in assignment.iterations),
    )
    if optimisation is not None:
        _csv(
            out / "optimisation_candidates.csv",
            (
                {
                    **asdict(row),
                    "phase_durations_s": "|".join(map(str, row.phase_durations_s)),
                }
                for row in optimisation.candidates
            ),
        )
        (out / "optimisation_summary.json").write_text(
            json.dumps(data["optimisation"], indent=2), encoding="utf-8"
        )
    return data
