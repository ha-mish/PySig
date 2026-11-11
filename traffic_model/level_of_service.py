"""Signalised-intersection level-of-service helpers."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LOSResult:
    grade: str | None
    standard: str
    basis: str
    status: str


def signalized_level_of_service(
    delay_seconds, standard="hcm_signalized", basis="queueing_delay_seconds_per_pcu"
):
    """Classify delay, clearly distinguishing screening from HCM control delay."""
    if delay_seconds is None:
        return LOSResult(None, standard, basis, "unavailable")
    if standard != "hcm_signalized":
        raise ValueError(f"Unsupported LOS standard: {standard}")
    limits = ((10, "A"), (20, "B"), (35, "C"), (55, "D"), (80, "E"))
    grade = next((g for limit, g in limits if delay_seconds <= limit), "F")
    status = "formal" if basis == "control_delay_seconds_per_vehicle" else "screening"
    return LOSResult(grade, standard, basis, status)
