from traffic_model.dynamic_rr67 import (
    assigned_turning_proportion,
    dynamic_rr67_result,
)


def fake_saturation(definition):
    base = 2000.0
    proportion = float(definition.get("turning_proportion", 0.0))
    radius = float(definition.get("turning_radius_m", 20.0))
    return base / (1.0 + proportion / radius)


def lane(definition=None):
    return {
        "id": "L1",
        "saturation_flow": definition
        or {
            "method": "rr67_unopposed",
            "lane_width_m": 3.2,
            "turning_radius_m": 20.0,
        },
    }


MOVEMENTS = {
    "T": {"from_lane_id": "L1", "movement_type": "through"},
    "R": {"from_lane_id": "L1", "movement_type": "right"},
}


def test_turning_proportion_is_derived_from_assignment():
    total, turning, proportion = assigned_turning_proportion(
        lane(), MOVEMENTS, {"T": 800.0, "R": 200.0}
    )
    assert total == 1000.0
    assert turning == 200.0
    assert proportion == 0.2


def test_dynamic_rr67_uses_assigned_proportion():
    result = dynamic_rr67_result(
        lane(),
        MOVEMENTS,
        {"T": 750.0, "R": 250.0},
        saturation_function=fake_saturation,
    )
    assert result.turning_proportion == 0.25
    assert result.turning_proportion_source == "assigned_movement_flows"
    assert result.rr67_definition["turning_proportion"] == 0.25


def test_legacy_fixed_turning_proportion_remains_an_override():
    definition = {
        "method": "rr67_unopposed",
        "turning_proportion": 0.4,
        "turning_radius_m": 20.0,
    }
    result = dynamic_rr67_result(
        lane(definition),
        MOVEMENTS,
        {"T": 900.0, "R": 100.0},
        saturation_function=fake_saturation,
    )
    assert result.turning_proportion == 0.4
    assert result.turning_proportion_source == "legacy_fixed_input"


def test_movement_radii_are_flow_weighted():
    movements = {
        "R1": {
            "from_lane_id": "L1",
            "movement_type": "right",
            "turning_radius_m": 10.0,
        },
        "R2": {
            "from_lane_id": "L1",
            "movement_type": "right",
            "turning_radius_m": 30.0,
        },
    }
    result = dynamic_rr67_result(
        lane(),
        movements,
        {"R1": 100.0, "R2": 300.0},
        saturation_function=fake_saturation,
    )
    assert result.turning_radius_m == 25.0
    assert result.turning_radius_source == "assigned_movement_weighted"
