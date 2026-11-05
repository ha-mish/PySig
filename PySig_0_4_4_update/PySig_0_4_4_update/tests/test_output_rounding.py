"""Regression tests for human-readable output rounding."""

from traffic_model.output_rounding import round_output


def test_operational_values_round_to_two_decimals():
    data = {"maximum_queue_m": 61.04583333333333}
    assert round_output(data)["maximum_queue_m"] == 61.05


def test_diagnostics_retain_six_decimals():
    data = {"od_conservation_error": 0.0000006}
    assert round_output(data)["od_conservation_error"] == 0.000001


def test_booleans_are_not_converted_to_numbers():
    data = {"assignment_converged": True}
    assert round_output(data)["assignment_converged"] is True
