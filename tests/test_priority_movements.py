from dataclasses import replace
from pathlib import Path
from traffic_model.conflicts import active_capacity_factor
from traffic_model.domain import MovementConflict
from traffic_model.loader import load_model

ROOT = Path(__file__).resolve().parents[1]


def test_priority_inactive_factor_is_one():
    model = load_model(ROOT / "configs" / "example_intersection_optimisation.yaml")
    model = replace(
        model, conflicts=(MovementConflict("M_W_RIGHT", ("M_N_THROUGH",), 0.4),)
    )
    assert active_capacity_factor(model, "M_W_RIGHT", {"M_W_RIGHT"}) == 1.0


def test_priority_active_factor_is_configured_value():
    model = load_model(ROOT / "configs" / "example_intersection_optimisation.yaml")
    model = replace(
        model, conflicts=(MovementConflict("M_W_RIGHT", ("M_N_THROUGH",), 0.4),)
    )
    active = {"M_W_RIGHT", "M_N_THROUGH"}
    assert active_capacity_factor(model, "M_W_RIGHT", active) == 0.4
