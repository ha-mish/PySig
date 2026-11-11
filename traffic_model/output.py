"""Output writers for PySig 0.4.4.

Operational values are rounded to two decimal places for readability.
Convergence and conservation diagnostics retain six decimal places.
Rounding occurs only during serialisation: simulation, assignment and
optimisation calculations retain full floating-point precision.
"""

from dataclasses import asdict
from pathlib import Path
import csv
import json
from .level_of_service import signalized_level_of_service
from .rr67 import calculation_audit

OPERATIONAL_DECIMALS = 2
DIAGNOSTIC_DECIMALS = 6

DIAGNOSTIC_FIELDS = {
    "conservation_error",
    "od_conservation_error",
    "maximum_flow_change",
    "assignment_maximum_flow_change",
    "relative_gap",
}


def round_output(value, key=None):
    """Recursively round values for human-readable serialised output."""

    # bool is a subclass of int, so preserve it before numeric handling.
    if isinstance(value, bool):
        return value

    if isinstance(value, float):
        digits = (
            DIAGNOSTIC_DECIMALS if key in DIAGNOSTIC_FIELDS else OPERATIONAL_DECIMALS
        )
        return round(value, digits)

    if isinstance(value, dict):
        return {
            item_key: round_output(item_value, item_key)
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [round_output(item) for item in value]

    return value


def _csv(path, rows):
    """Write dictionaries to CSV when at least one row exists."""

    rows = list(rows)
    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _controller_dict(controller):
    """Return a serialisable controller representation."""

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
    """Build the complete machine-readable PySig result."""

    controllers = controllers or model.controllers
    simulation = assignment.simulation

    movements = []
    for row in simulation.movements.values():
        serialised = asdict(row)
        los = signalized_level_of_service(
            row.mean_delay_seconds_per_pcu,
            model.los_standard,
            model.los_basis,
        )
        serialised.update(
            {
                "level_of_service": los.grade,
                "level_of_service_standard": los.standard,
                "level_of_service_basis": los.basis,
                "level_of_service_status": los.status,
                "saturation_flow_calculation": calculation_audit(
                    model.lanes[row.lane_id].saturation_flow
                ),
            }
        )
        movements.append(serialised)
    lanes = []
    for row in simulation.lanes.values():
        serialised = asdict(row)
        los = signalized_level_of_service(
            row.mean_delay_seconds_per_pcu,
            model.los_standard,
            model.los_basis,
        )
        serialised.update(
            {
                "level_of_service": los.grade,
                "level_of_service_standard": los.standard,
                "level_of_service_basis": los.basis,
                "level_of_service_status": los.status,
                "saturation_flow_calculation": calculation_audit(
                    model.lanes[row.lane_id].saturation_flow
                ),
            }
        )
        lanes.append(serialised)

    total_demand = sum(model.od.values())
    total_departures = sum(row.departures_pcu for row in simulation.lanes.values())

    mean_delay = (
        simulation.network_delay_pcu_hours * 3600.0 / total_departures
        if total_departures > 0
        else 0.0
    )

    max_simulated_lane_dos = max(
        (row.simulated_degree_of_saturation for row in simulation.lanes.values()),
        default=0.0,
    )

    nominal_dos_values = [
        row.nominal_degree_of_saturation
        for row in simulation.lanes.values()
        if row.nominal_degree_of_saturation is not None
    ]
    max_nominal_lane_dos = max(nominal_dos_values) if nominal_dos_values else None

    max_queue = max(
        (row.maximum_queue_pcu for row in simulation.lanes.values()),
        default=0.0,
    )
    max_queue_m = max(
        (row.maximum_queue_m for row in simulation.lanes.values()),
        default=0.0,
    )

    conservation_error = (
        assignment.iterations[-1].conservation_error if assignment.iterations else 0.0
    )

    intersections = []
    for intersection_id, intersection in model.intersections.items():
        controller = controllers[intersection.controller_id]

        lane_rows = [
            asdict(row)
            for row in simulation.lanes.values()
            if row.intersection_id == intersection_id
        ]
        movement_rows = [
            asdict(simulation.movements[movement_id])
            for movement_id in intersection.movement_ids
            if movement_id in simulation.movements
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
        "schema_version": "0.4.5",
        "model_id": model.model_id,
        "model_name": model.model_name,
        "result_type": result_type,
        "run_mode": model.optimisation.mode,
        "methodology": {
            "calculation_method": model.calculation_method,
            "queue_model": "deterministic_time_sliced_shared_lane",
            "shared_lane_model": "fifo_composition",
            "effective_green_method": (
                "signal_green_minus_start_plus_end_displacement"
            ),
            "nominal_capacity_method": ("saturation_flow_times_effective_green_ratio"),
            "nominal_degree_of_saturation_method": ("demand_over_nominal_capacity"),
            "operational_output_decimals": OPERATIONAL_DECIMALS,
            "diagnostic_output_decimals": DIAGNOSTIC_DECIMALS,
        },
        "simulation": {
            "horizon_s": model.network.horizon_s,
            "time_slice_s": model.network.time_slice_s,
            "warm_up_s": model.network.warm_up_s,
            "pcu_length_m": model.pcu_length_m,
            "start_displacement_s": model.start_displacement_s,
            "end_displacement_s": model.end_displacement_s,
            "queue_kernel": "shared_lane_queue_composition",
        },
        "summary": {
            "total_od_demand_pcu_per_hour": total_demand,
            "network_delay_pcu_hours": simulation.network_delay_pcu_hours,
            "mean_delay_seconds_per_departed_pcu": mean_delay,
            "maximum_nominal_lane_degree_of_saturation": (max_nominal_lane_dos),
            "maximum_simulated_lane_degree_of_saturation": (max_simulated_lane_dos),
            "maximum_queue_pcu": max_queue,
            "maximum_queue_m": max_queue_m,
            "maximum_lane_storage_utilisation": (
                simulation.maximum_lane_storage_utilisation
            ),
            "maximum_link_storage_utilisation": (
                simulation.maximum_link_storage_utilisation
            ),
            "assignment_converged": assignment.converged,
            "assignment_iterations": len(assignment.iterations),
            "od_conservation_error": conservation_error,
            "od_conservation_pass": (
                conservation_error <= model.assignment.conservation_tolerance
            ),
        },
        "lanes": lanes,
        "movements": movements,
        "intersections": intersections,
        "links": [asdict(row) for row in simulation.links.values()],
        "routes": [
            {
                "route_id": route_id,
                "origin_zone_id": model.routes[route_id].origin_zone_id,
                "destination_zone_id": (model.routes[route_id].destination_zone_id),
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
    """Write PySig JSON and CSV outputs."""

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    data = rich_result(
        model,
        assignment,
        controllers,
        optimisation,
        result_type,
    )
    data = round_output(data)

    (out / "results.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    _csv(
        out / "lane_results.csv",
        (round_output(asdict(row)) for row in assignment.simulation.lanes.values()),
    )

    _csv(
        out / "movement_results.csv",
        (round_output(asdict(row)) for row in assignment.simulation.movements.values()),
    )

    _csv(
        out / "route_assignment.csv",
        (
            round_output(
                {
                    "route_id": route_id,
                    "origin_zone_id": (model.routes[route_id].origin_zone_id),
                    "destination_zone_id": (model.routes[route_id].destination_zone_id),
                    "assigned_flow_pcu_per_hour": flow,
                    "movement_path": " > ".join(model.routes[route_id].movement_ids),
                }
            )
            for route_id, flow in assignment.route_flows.items()
        ),
    )

    _csv(
        out / "network_links.csv",
        (round_output(asdict(row)) for row in assignment.simulation.links.values()),
    )

    _csv(
        out / "assignment_iterations.csv",
        (round_output(asdict(row)) for row in assignment.iterations),
    )

    if optimisation is not None:
        _csv(
            out / "optimisation_candidates.csv",
            (
                round_output(
                    {
                        **asdict(row),
                        "phase_durations_s": "|".join(map(str, row.phase_durations_s)),
                    }
                )
                for row in optimisation.candidates
            ),
        )

        (out / "optimisation_summary.json").write_text(
            json.dumps(
                data["optimisation"],
                indent=2,
            ),
            encoding="utf-8",
        )

    return data
