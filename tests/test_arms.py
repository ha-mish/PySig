"""Regression tests for explicit intersection arms."""

from traffic_model.arms import parse_arms, validate_relation


def test_nested_arms_are_flattened():
    data = [
        {
            "id": "I1",
            "arms": [
                {
                    "id": "A1",
                    "name": "Canning Highway",
                    "direction": "E/B",
                    "relation": "Entry",
                },
                {
                    "id": "A2",
                    "name": "Canning Highway",
                    "direction": "W/B",
                    "relation": "Exit",
                },
            ],
        }
    ]
    arms, by_intersection = parse_arms(data)
    assert arms["A1"].name == "Canning Highway"
    assert arms["A1"].relation == "Entry"
    assert by_intersection["I1"] == ("A1", "A2")


def test_arm_relation_is_constrained():
    try:
        validate_relation("Internal")
    except ValueError:
        return
    raise AssertionError("Invalid arm relation was accepted")
