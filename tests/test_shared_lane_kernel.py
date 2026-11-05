from dataclasses import replace
from pathlib import Path

import pytest

from traffic_model.loader import load_model
from traffic_model.simulation import simulate

ROOT = Path(__file__).resolve().parents[1]

CONFIG = (
    ROOT
    / "configs"
    / "example_intersection_optimisation.yaml"
)


def shared_lane_model(
    different_signal_groups=False,
):
    """Return a model with two movements sharing W_1."""

    model = load_model(CONFIG)

    movements = dict(
        model.movements
    )

    right = movements[
        "M_W_RIGHT"
    ]

    movements["M_W_RIGHT"] = replace(
        right,
        from_lane_id="W_1",
        signal_group_id=(
            "SG_NS"
            if different_signal_groups
            else "SG_EW"
        ),
    )

    return replace(
        model,
        movements=movements,
    )


def test_same_lane_movement_demands_sum_to_lane_demand():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    assert (
        lane.demand_pcu_per_hour
        == pytest.approx(600.0)
    )

    movement_arrivals = (
        result
        .movements["M_W_THROUGH"]
        .arrivals_pcu
        + result
        .movements["M_W_RIGHT"]
        .arrivals_pcu
    )

    assert (
        lane.arrivals_pcu
        == pytest.approx(
            movement_arrivals
        )
    )


def test_shared_lane_queue_and_delay_are_conserved():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    movements = [
        result.movements[
            "M_W_THROUGH"
        ],
        result.movements[
            "M_W_RIGHT"
        ],
    ]

    assert (
        lane.final_queue_pcu
        == pytest.approx(
            sum(
                movement.final_queue_pcu
                for movement in movements
            )
        )
    )

    assert (
        lane.total_delay_pcu_hours
        == pytest.approx(
            sum(
                movement.total_delay_pcu_hours
                for movement in movements
            )
        )
    )

    assert (
        lane.departures_pcu
        == pytest.approx(
            sum(
                movement.departures_pcu
                for movement in movements
            )
        )
    )


def test_shared_lane_has_one_simulated_service_capacity():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 1000.0,
            "M_W_RIGHT": 1000.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    through = result.movements[
        "M_W_THROUGH"
    ]

    right = result.movements[
        "M_W_RIGHT"
    ]

    movement_capacity = (
        through
        .simulated_service_capacity_pcu_per_hour
        + right
        .simulated_service_capacity_pcu_per_hour
    )

    assert movement_capacity == pytest.approx(
        lane
        .simulated_service_capacity_pcu_per_hour
    )

    assert (
        lane
        .simulated_service_capacity_pcu_per_hour
        <= lane.saturation_flow_pcu_per_hour
        + 1e-6
    )


def test_shared_lane_nominal_capacity_not_duplicated():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    assert lane.signal_group_ids == (
        "SG_EW",
    )

    assert (
        lane.nominal_capacity_pcu_per_hour
        is not None
    )

    expected_capacity = (
        lane.saturation_flow_pcu_per_hour
        * lane.effective_green_ratio
    )

    assert (
        lane.nominal_capacity_pcu_per_hour
        == pytest.approx(
            expected_capacity
        )
    )


def test_shared_lane_nominal_dos_uses_total_lane_demand():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    expected_dos = (
        lane.demand_pcu_per_hour
        / lane.nominal_capacity_pcu_per_hour
    )

    assert (
        lane.nominal_degree_of_saturation
        == pytest.approx(
            expected_dos
        )
    )


def test_shared_lane_green_uses_displacements():
    model = shared_lane_model()

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    expected_effective_green = (
        lane.signal_green_s
        - model.start_displacement_s
        + model.end_displacement_s
    )

    expected_effective_green = min(
        lane.cycle_time_s,
        max(
            0.0,
            expected_effective_green,
        ),
    )

    assert (
        lane.effective_green_s
        == pytest.approx(
            expected_effective_green
        )
    )


def test_equal_displacements_preserve_green_duration():
    model = shared_lane_model()

    assert model.start_displacement_s == pytest.approx(
        model.end_displacement_s
    )

    result = simulate(
        model,
        {
            "M_W_THROUGH": 500.0,
            "M_W_RIGHT": 100.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    assert (
        lane.effective_green_s
        == pytest.approx(
            lane.signal_green_s
        )
    )


def test_different_signal_groups_use_one_lane_storage():
    model = shared_lane_model(
        different_signal_groups=True
    )

    result = simulate(
        model,
        {
            "M_W_THROUGH": 450.0,
            "M_W_RIGHT": 150.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    assert (
        lane.maximum_queue_pcu
        <= model.lanes["W_1"].storage_pcu
        + 1e-9
    )

    assert (
        lane.maximum_queue_pcu
        >= max(
            result
            .movements["M_W_THROUGH"]
            .maximum_queue_pcu,
            result
            .movements["M_W_RIGHT"]
            .maximum_queue_pcu,
        )
    )


def test_multi_signal_group_lane_has_no_single_nominal_capacity():
    model = shared_lane_model(
        different_signal_groups=True
    )

    result = simulate(
        model,
        {
            "M_W_THROUGH": 450.0,
            "M_W_RIGHT": 150.0,
            "M_N_THROUGH": 0.0,
        },
    )

    lane = result.lanes["W_1"]

    assert set(
        lane.signal_group_ids
    ) == {
        "SG_EW",
        "SG_NS",
    }

    assert lane.signal_green_s is None

    assert lane.effective_green_s is None

    assert (
        lane.effective_green_ratio
        is None
    )

    assert (
        lane.nominal_capacity_pcu_per_hour
        is None
    )

    assert (
        lane.nominal_degree_of_saturation
        is None
    )