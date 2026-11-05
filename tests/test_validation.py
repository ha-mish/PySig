from pathlib import Path
from dataclasses import replace
from traffic_model.loader import load_model
from traffic_model.validation import validate

ROOT = Path(__file__).resolve().parents[1]


def test_missing_to_lane_detected():
    m = load_model(ROOT / "configs" / "example_intersection_optimisation.yaml")
    moves = dict(m.movements)
    moves["M_W_THROUGH"] = replace(moves["M_W_THROUGH"], to_lane_id="DOES_NOT_EXIST")
    m = replace(m, movements=moves)
    assert any("to_lane_id" in x for x in validate(m))
