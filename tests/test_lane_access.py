import pytest

from traffic_model.lane_access import (
    build_lane_access_trees,
    lane_storage_pcu,
    solve_lane_access_tree,
    validate_lane_access_hierarchy,
)


def nested_lanes():
    return {
        "P": {
            "id": "P",
            "intersection_id": "I1",
            "arm_id": "A1",
            "physical_length_m": 245.0,
            "parent_lane_id": None,
        },
        "S": {
            "id": "S",
            "intersection_id": "I1",
            "arm_id": "A1",
            "physical_length_m": 70.0,
            "parent_lane_id": "P",
        },
        "N": {
            "id": "N",
            "intersection_id": "I1",
            "arm_id": "A1",
            "physical_length_m": 35.0,
            "parent_lane_id": "S",
        },
    }


def test_actual_lane_length_determines_each_lane_storage():
    lanes = nested_lanes()
    assert lane_storage_pcu(lanes["S"], 7.0) == 10.0
    assert lane_storage_pcu(lanes["N"], 7.0) == 5.0


def test_nested_lane_access_tree_is_constructed():
    tree = build_lane_access_trees(nested_lanes(), 7.0)[0]
    assert tree.root_lane_id == "P"
    assert tree.maximum_depth == 2
    assert tree.nodes["P"].child_lane_ids == ("S",)
    assert tree.nodes["S"].child_lane_ids == ("N",)


def test_child_must_be_shorter_than_parent():
    lanes = nested_lanes()
    lanes["N"]["physical_length_m"] = 80.0
    with pytest.raises(ValueError, match="less than parent"):
        validate_lane_access_hierarchy(lanes)


def test_parent_cycles_are_rejected():
    lanes = nested_lanes()
    lanes["P"]["parent_lane_id"] = "N"
    with pytest.raises(ValueError, match="cycle"):
        validate_lane_access_hierarchy(lanes)


def test_nested_short_lanes_add_only_storage_limited_cycle_capacity():
    tree = build_lane_access_trees(nested_lanes(), 7.0)[0]
    result = solve_lane_access_tree(
        tree,
        {"P": 1000.0, "S": 500.0, "N": 300.0},
        {"P": 1000.0, "S": 800.0, "N": 700.0},
        cycle_time_s=70.0,
    )
    # Storage-equivalent boosts: S=10*3600/70 and N=5*3600/70.
    assert result.short_lane_storage_boost_pcu_per_hour["S"] == pytest.approx(
        514.285714
    )
    assert result.short_lane_storage_boost_pcu_per_hour["N"] == pytest.approx(
        257.142857
    )
    assert result.tree_accessible_capacity_pcu_per_hour == pytest.approx(
        1771.428571
    )
    assert sum(result.lane_accessible_capacity_pcu_per_hour.values()) == pytest.approx(
        result.tree_accessible_capacity_pcu_per_hour
    )


def test_parent_capacity_is_affected_by_tree_allocation():
    tree = build_lane_access_trees(nested_lanes(), 7.0)[0]
    result = solve_lane_access_tree(
        tree,
        {"P": 1000.0, "S": 500.0, "N": 300.0},
        {"P": 1000.0, "S": 800.0, "N": 700.0},
        cycle_time_s=70.0,
    )
    assert result.lane_accessible_capacity_pcu_per_hour["P"] < 1000.0
    assert result.lane_degree_of_saturation["P"] == pytest.approx(
        result.lane_degree_of_saturation["S"]
    )
