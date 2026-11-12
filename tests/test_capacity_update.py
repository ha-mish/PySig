from traffic_model.capacity_update import update_dynamic_capacities


def fake_saturation(definition):
    return 1800.0 / (
        1.0
        + float(definition.get("turning_proportion", 0.0))
        / float(definition.get("turning_radius_m", 20.0))
    )


def test_capacity_update_combines_assignment_rr67_and_nested_lane_access():
    lanes = {
        "P": {
            "id": "P",
            "intersection_id": "I1",
            "arm_id": "A1",
            "physical_length_m": 210.0,
            "saturation_flow": {
                "method": "rr67_unopposed",
                "turning_radius_m": 20.0,
            },
        },
        "S": {
            "id": "S",
            "intersection_id": "I1",
            "arm_id": "A1",
            "parent_lane_id": "P",
            "physical_length_m": 42.0,
            "saturation_flow": {
                "method": "rr67_unopposed",
                "turning_radius_m": 12.0,
            },
        },
    }
    movements = {
        "PT": {"from_lane_id": "P", "movement_type": "through"},
        "PR": {"from_lane_id": "P", "movement_type": "right"},
        "SR": {"from_lane_id": "S", "movement_type": "right"},
    }
    update = update_dynamic_capacities(
        lanes,
        movements,
        {"PT": 700.0, "PR": 300.0, "SR": 400.0},
        {"P": 0.5, "S": 0.5},
        {"P": 70.0, "S": 70.0},
        pcu_length_m=7.0,
        saturation_function=fake_saturation,
    )
    assert update.rr67_by_lane["P"].turning_proportion == 0.3
    assert update.rr67_by_lane["S"].turning_proportion == 1.0
    assert "P" in update.lane_access_by_root
    assert (
        sum(update.accessible_capacity_pcu_per_hour.values())
        == update.lane_access_by_root["P"].tree_accessible_capacity_pcu_per_hour
    )
