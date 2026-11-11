from dataclasses import replace
from pathlib import Path
import pytest
from traffic_model.calculation.analytical.queue import solve_interval
from traffic_model.calculation import calculate
from traffic_model.loader import load_model

ROOT = Path(__file__).resolve().parents[1]


def test_exact_queue_growth_and_area():
    result = solve_interval(0.0, 2.0, 1.0, 10.0)
    assert result.final_queue == pytest.approx(10.0)
    assert result.delay_pcu_seconds == pytest.approx(50.0)


def test_exact_part_interval_clearance():
    result = solve_interval(10.0, 1.0, 2.0, 20.0)
    assert result.final_queue == pytest.approx(0.0)
    assert result.delay_pcu_seconds == pytest.approx(50.0)


def test_analytical_method_is_selectable():
    model = load_model(ROOT / "configs" / "example_intersection_optimisation.yaml")
    # Use one independent movement to exercise the initial supported scope.
    movement = model.movements["M_N_THROUGH"]
    model = replace(
        model,
        calculation_method="analytical",
        movements={movement.movement_id: movement},
        lanes={movement.from_lane_id: model.lanes[movement.from_lane_id]},
        intersections={
            "I1": replace(
                model.intersections["I1"], movement_ids=(movement.movement_id,)
            )
        },
        links={},
    )
    result = calculate(model, {movement.movement_id: 350.0})
    assert result.calculation_method == "analytical"
    assert result.movements[movement.movement_id].arrivals_pcu == pytest.approx(87.5)
