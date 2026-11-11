"""Analytical shared-lane regression tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from traffic_model.calculation import calculate
from traffic_model.loader import load_model


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "example_intersection_optimisation.yaml"


def shared_lane_model():
    model = load_model(CONFIG)
    movements = dict(model.movements)
    right = movements["M_W_RIGHT"]
    movements["M_W_RIGHT"] = replace(
        right,
        from_lane_id="W_1",
        signal_group_id="SG_EW",
    )
    return replace(
        model,
        calculation_method="analytical",
        movements=movements,
        links={},
        conflicts=(),
    )


def test_analytical_result_has_common_utilisation_fields():
    model = shared_lane_model()
    result = calculate(
        model,
        {"M_W_THROUGH": 500.0, "M_W_RIGHT": 100.0, "M_N_THROUGH": 0.0},
    )
    assert result.maximum_lane_storage_utilisation >= 0.0
    assert result.maximum_link_storage_utilisation == 0.0
    assert result.links == {}


def test_shared_lane_demand_and_queue_conservation():
    model = shared_lane_model()
    result = calculate(
        model,
        {"M_W_THROUGH": 500.0, "M_W_RIGHT": 100.0, "M_N_THROUGH": 0.0},
    )
    lane = result.lanes["W_1"]
    movements = [result.movements[mid] for mid in lane.movement_ids]
    assert lane.demand_pcu_per_hour == pytest.approx(600.0)
    assert lane.final_queue_pcu == pytest.approx(
        sum(row.final_queue_pcu for row in movements)
    )
    assert lane.total_delay_pcu_hours == pytest.approx(
        sum(row.total_delay_pcu_hours for row in movements)
    )
    assert lane.departures_pcu == pytest.approx(
        sum(row.departures_pcu for row in movements)
    )


def test_shared_lane_capacity_is_not_duplicated():
    model = shared_lane_model()
    result = calculate(
        model,
        {"M_W_THROUGH": 1000.0, "M_W_RIGHT": 1000.0, "M_N_THROUGH": 0.0},
    )
    lane = result.lanes["W_1"]
    movement_capacity = sum(
        result.movements[mid].simulated_service_capacity_pcu_per_hour
        for mid in lane.movement_ids
    )
    assert movement_capacity == pytest.approx(
        lane.simulated_service_capacity_pcu_per_hour
    )
