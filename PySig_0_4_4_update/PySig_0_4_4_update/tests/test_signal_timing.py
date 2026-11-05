"""Regression tests for PySig 0.4.4 signal timing definitions."""

import pytest

from traffic_model.timing import (
    effective_green_seconds,
    nominal_capacity_pcu_per_hour,
    nominal_degree_of_saturation,
)


def test_equal_displacements_preserve_effective_green():
    assert effective_green_seconds(55.0, 60.0, 3.0, 3.0) == pytest.approx(55.0)


def test_unequal_displacements_change_effective_green():
    assert effective_green_seconds(55.0, 60.0, 3.0, 2.0) == pytest.approx(54.0)


def test_effective_green_is_bounded_by_cycle():
    assert effective_green_seconds(58.0, 60.0, 0.0, 5.0) == pytest.approx(60.0)


def test_nominal_capacity_uses_effective_green_ratio():
    effective_green_ratio = 55.0 / 60.0
    value = nominal_capacity_pcu_per_hour(1900.0, effective_green_ratio)
    assert value == pytest.approx(1741.6666666667)


def test_nominal_dos_uses_nominal_capacity():
    capacity = nominal_capacity_pcu_per_hour(1900.0, 55.0 / 60.0)
    value = nominal_degree_of_saturation(1000.0, capacity)
    assert value == pytest.approx(0.5741626794)


def test_zero_capacity_with_demand_is_reported_as_oversaturated():
    assert nominal_degree_of_saturation(100.0, 0.0) == 999.0
