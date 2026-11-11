"""Tests for PySig 0.4.5a agro-arrow shared-lane analysis."""

from dataclasses import replace
from pathlib import Path

import pytest

from traffic_model.calculation import calculate
from traffic_model.calculation.analytical.shared_lane import (
    expected_discharge_before_blocking,
    front_blocking_state,
)
from traffic_model.loader import load_model


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "example_intersection_optimisation.yaml"


def agro_arrow_model():
    model = load_model(CONFIG)
    movements = dict(model.movements)
    right = movements["M_W_RIGHT"]
    movements["M_W_RIGHT"] = replace(
        right,
        from_lane_id="W_1",
        signal_group_id="SG_NS",
    )
    return replace(
        model,
        calculation_method="analytical",
        movements=movements,
        links={},
        conflicts=(),
    )


def test_80_20_expected_discharge_before_blocking_is_four():
    assert expected_discharge_before_blocking(0.8, 0.2) == pytest.approx(4.0)


def test_no_blocked_movement_has_full_interval_service():
    state = front_blocking_state(
        {"through": 8.0, "turn": 0.0},
        {"through": 800.0, "turn": 0.0},
        {"through"},
        1900.0 / 3600.0,
        20.0,
    )
    assert not state.blocking_applies
    assert state.service_duration_before_blocking_s == pytest.approx(20.0)


def test_analytical_agro_arrow_runs_and_preserves_lane_accounting():
    model = agro_arrow_model()
    result = calculate(
        model,
        {"M_W_THROUGH": 800.0, "M_W_RIGHT": 200.0, "M_N_THROUGH": 0.0},
    )
    lane = result.lanes["W_1"]
    assert lane.shared_lane_model == "geometric_front_blocking"
    assert lane.demand_pcu_per_hour == pytest.approx(1000.0)
    assert lane.final_queue_pcu == pytest.approx(
        sum(result.movements[mid].final_queue_pcu for mid in lane.movement_ids)
    )
    assert lane.departures_pcu == pytest.approx(
        sum(result.movements[mid].departures_pcu for mid in lane.movement_ids)
    )
    assert lane.total_delay_pcu_hours == pytest.approx(
        sum(result.movements[mid].total_delay_pcu_hours for mid in lane.movement_ids)
    )
    assert result.maximum_lane_storage_utilisation >= 0.0
    assert result.maximum_link_storage_utilisation == 0.0
