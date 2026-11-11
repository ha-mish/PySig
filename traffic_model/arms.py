"""Arm helpers and legacy lane-to-arm inference."""

import re
import warnings

from .domain import Arm


VALID_ARM_RELATIONS = {"Entry", "Exit"}
_ARM_PREFIX = re.compile(r"^(A[^_]+)_")


def validate_relation(value):
    if value not in VALID_ARM_RELATIONS:
        expected = ", ".join(sorted(VALID_ARM_RELATIONS))
        raise ValueError(f"Arm relation {value!r} is invalid; expected {expected}")
    return value


def parse_arms(intersections_data):
    """Flatten nested YAML arm definitions into model dictionaries."""
    arms = {}
    arm_ids_by_intersection = {}
    for intersection in intersections_data:
        intersection_id = intersection["id"]
        ids = []
        for row in intersection.get("arms", []):
            arm_id = row["id"]
            if arm_id in arms:
                raise ValueError(f"Duplicate arm id: {arm_id}")
            relation = validate_relation(str(row["relation"]))
            arm = Arm(
                arm_id=arm_id,
                intersection_id=intersection_id,
                name=str(row.get("name", arm_id)),
                direction=str(row.get("direction", "")),
                relation=relation,
                bearing_degrees=(
                    float(row["bearing_degrees"])
                    if row.get("bearing_degrees") is not None
                    else None
                ),
            )
            arms[arm_id] = arm
            ids.append(arm_id)
        arm_ids_by_intersection[intersection_id] = tuple(ids)
    return arms, arm_ids_by_intersection


def infer_legacy_arm_id(lane_id, intersection_id, arms):
    """Infer A1 from legacy lane IDs such as A1_1 or A1_1L when possible."""
    match = _ARM_PREFIX.match(lane_id)
    if not match:
        return None
    arm_id = match.group(1)
    arm = arms.get(arm_id)
    if arm and arm.intersection_id == intersection_id:
        warnings.warn(
            f"Lane {lane_id} does not declare arm_id; inferred {arm_id}. "
            "Explicit arm_id is recommended.",
            DeprecationWarning,
            stacklevel=2,
        )
        return arm_id
    return None
