import json
from pathlib import Path

import pytest

from traffic_model.assignment import assign
from traffic_model.loader import load_model
from traffic_model.output import write_outputs

ROOT = Path(__file__).resolve().parents[1]

CONFIG = ROOT / "configs" / "example_intersection_optimisation.yaml"


REQUIRED_MOVEMENT_FIELDS = {
    "movement_id",
    "intersection_id",
    "lane_id",
    "to_lane_id",
    "signal_group_id",
    "movement_type",
    "demand_pcu_per_hour",
    "saturation_flow_pcu_per_hour",
    "cycle_time_s",
    "signal_green_s",
    "start_displacement_s",
    "end_displacement_s",
    "effective_green_s",
    "effective_green_ratio",
    "nominal_capacity_pcu_per_hour",
    "nominal_degree_of_saturation",
    "simulated_service_capacity_pcu_per_hour",
    "simulated_degree_of_saturation",
    "arrivals_pcu",
    "departures_pcu",
    "final_queue_pcu",
    "maximum_queue_pcu",
    "maximum_queue_m",
    "total_delay_pcu_hours",
    "mean_delay_seconds_per_pcu",
    "unserved_demand_pcu",
    "storage_overflow_pcu",
    "storage_full_seconds",
    "capacity_method",
}


REQUIRED_LANE_FIELDS = {
    "lane_id",
    "intersection_id",
    "movement_ids",
    "signal_group_ids",
    "demand_pcu_per_hour",
    "saturation_flow_pcu_per_hour",
    "cycle_time_s",
    "signal_green_s",
    "start_displacement_s",
    "end_displacement_s",
    "effective_green_s",
    "effective_green_ratio",
    "nominal_capacity_pcu_per_hour",
    "nominal_degree_of_saturation",
    "simulated_service_capacity_pcu_per_hour",
    "simulated_degree_of_saturation",
    "arrivals_pcu",
    "departures_pcu",
    "final_queue_pcu",
    "maximum_queue_pcu",
    "maximum_queue_m",
    "total_delay_pcu_hours",
    "mean_delay_seconds_per_pcu",
    "unserved_demand_pcu",
    "storage_pcu",
    "storage_utilisation",
    "storage_overflow_pcu",
    "storage_full_seconds",
    "capacity_method",
}


def load_example():
    """Load the standard intersection test model."""

    return load_model(CONFIG)


def run_example():
    """Load and assign the standard intersection test model."""

    model = load_example()
    assignment = assign(model)

    return model, assignment


def test_rich_results_json(tmp_path):
    model, assignment = run_example()

    write_outputs(
        model,
        assignment,
        tmp_path,
    )

    result_file = tmp_path / "results.json"

    assert result_file.exists()

    data = json.loads(result_file.read_text(encoding="utf-8"))

    assert data["schema_version"] == "0.4.4"

    assert data["lanes"]
    assert data["movements"]

    assert REQUIRED_LANE_FIELDS <= set(data["lanes"][0])

    assert REQUIRED_MOVEMENT_FIELDS <= set(data["movements"][0])


def test_expected_output_files_are_written(tmp_path):
    model, assignment = run_example()

    write_outputs(
        model,
        assignment,
        tmp_path,
    )

    assert (tmp_path / "results.json").exists()

    assert (tmp_path / "lane_results.csv").exists()

    assert (tmp_path / "movement_results.csv").exists()

    assert (tmp_path / "route_assignment.csv").exists()

    assert (tmp_path / "assignment_iterations.csv").exists()


def test_results_report_methodology(tmp_path):
    model, assignment = run_example()

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    methodology = data["methodology"]

    assert methodology["queue_model"] == ("deterministic_time_sliced_shared_lane")

    assert methodology["shared_lane_model"] == ("fifo_composition")

    assert methodology["effective_green_method"] == (
        "signal_green_minus_start_plus_end_displacement"
    )

    assert methodology["nominal_capacity_method"] == (
        "saturation_flow_times_effective_green_ratio"
    )

    assert (
        methodology["nominal_degree_of_saturation_method"]
        == "demand_over_nominal_capacity"
    )

    assert methodology["operational_output_decimals"] == 2

    assert methodology["diagnostic_output_decimals"] == 6


def test_displacement_settings_are_reported(tmp_path):
    model, assignment = run_example()

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    simulation = data["simulation"]

    assert simulation["start_displacement_s"] == pytest.approx(
        model.start_displacement_s
    )

    assert simulation["end_displacement_s"] == pytest.approx(model.end_displacement_s)


def test_signal_green_excludes_intergreen():
    model, assignment = run_example()

    movement = next(iter(assignment.simulation.movements.values()))

    controller = model.controllers[
        model.intersections[movement.intersection_id].controller_id
    ]

    active_phase_green = sum(
        phase.duration_s
        for phase in controller.phases
        if movement.signal_group_id in phase.active_signal_groups
    )

    assert movement.signal_green_s == pytest.approx(active_phase_green)


def test_effective_green_uses_displacements():
    model, assignment = run_example()

    movement = next(iter(assignment.simulation.movements.values()))

    expected = (
        movement.signal_green_s - model.start_displacement_s + model.end_displacement_s
    )

    expected = min(
        movement.cycle_time_s,
        max(
            0.0,
            expected,
        ),
    )

    assert movement.effective_green_s == pytest.approx(expected)


def test_nominal_capacity_is_auditable():
    _, assignment = run_example()

    movement = next(iter(assignment.simulation.movements.values()))

    expected_capacity = (
        movement.saturation_flow_pcu_per_hour * movement.effective_green_ratio
    )

    assert movement.nominal_capacity_pcu_per_hour == pytest.approx(expected_capacity)


def test_nominal_degree_of_saturation_is_auditable():
    _, assignment = run_example()

    movement = next(iter(assignment.simulation.movements.values()))

    if movement.nominal_capacity_pcu_per_hour > 0:
        expected_dos = (
            movement.demand_pcu_per_hour / movement.nominal_capacity_pcu_per_hour
        )
    elif movement.demand_pcu_per_hour > 0:
        expected_dos = 999.0
    else:
        expected_dos = 0.0

    assert movement.nominal_degree_of_saturation == pytest.approx(expected_dos)


def test_simulated_degree_of_saturation_is_auditable():
    _, assignment = run_example()

    movement = next(iter(assignment.simulation.movements.values()))

    capacity = movement.simulated_service_capacity_pcu_per_hour

    if capacity > 0:
        expected_dos = movement.demand_pcu_per_hour / capacity
    elif movement.demand_pcu_per_hour > 0:
        expected_dos = 999.0
    else:
        expected_dos = 0.0

    assert movement.simulated_degree_of_saturation == pytest.approx(expected_dos)


def test_to_lane_id_loaded_and_reported(tmp_path):
    model, assignment = run_example()

    movement = model.movements["M_W_THROUGH"]

    assert movement.to_lane_id == "E_OUT"

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    result = next(
        row for row in data["movements"] if row["movement_id"] == "M_W_THROUGH"
    )

    assert result["to_lane_id"] == "E_OUT"


def test_queue_metres_consistent():
    model, assignment = run_example()

    movement = assignment.simulation.movements["M_W_THROUGH"]

    assert movement.maximum_queue_m == pytest.approx(
        movement.maximum_queue_pcu * model.pcu_length_m
    )


def test_od_conservation_is_reported(tmp_path):
    model, assignment = run_example()

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    summary = data["summary"]

    assert summary["od_conservation_pass"]

    assert summary["od_conservation_error"] <= model.assignment.conservation_tolerance


def test_operational_json_outputs_are_rounded(tmp_path):
    model, assignment = run_example()

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    movement = data["movements"][0]

    value = movement["maximum_queue_m"]

    if isinstance(value, float):
        assert value == round(
            value,
            2,
        )


def test_summary_contains_both_dos_measures(
    tmp_path,
):
    model, assignment = run_example()

    data = write_outputs(
        model,
        assignment,
        tmp_path,
    )

    summary = data["summary"]

    assert "maximum_nominal_lane_degree_of_saturation" in summary

    assert "maximum_simulated_lane_degree_of_saturation" in summary
