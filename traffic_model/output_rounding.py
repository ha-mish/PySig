"""Output-only rounding helpers for PySig 0.4.4."""

from __future__ import annotations

OPERATIONAL_DECIMALS = 2
DIAGNOSTIC_DECIMALS = 6
DIAGNOSTIC_KEYS = {
    "conservation_error",
    "od_conservation_error",
    "od_conservation_error_pcu_per_hour",
    "maximum_flow_change",
    "assignment_maximum_flow_change",
    "relative_gap",
}


def round_output(value, key: str | None = None):
    """Recursively round serialised outputs without changing model calculations."""

    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        decimals = (
            DIAGNOSTIC_DECIMALS if key in DIAGNOSTIC_KEYS else OPERATIONAL_DECIMALS
        )
        return round(value, decimals)
    if isinstance(value, dict):
        return {
            item_key: round_output(item_value, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [round_output(item) for item in value]
    if isinstance(value, tuple):
        return [round_output(item) for item in value]
    return value
