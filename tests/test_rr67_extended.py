import pytest
from traffic_model.rr67 import rr67_result, saturation_flow


def test_gradient_reduces_flow():
    base = saturation_flow({"method": "rr67_unopposed"})
    uphill = saturation_flow({"method": "rr67_unopposed", "gradient_percent": 2})
    assert uphill == pytest.approx(base - 84)


def test_turning_radius_and_proportion_are_auditable():
    result = rr67_result(
        {"method": "rr67_unopposed", "turning_proportion": 0.5, "turning_radius_m": 15}
    )
    assert result.turning_divisor == pytest.approx(1.05)
    assert result.saturation_flow_pcu_per_hour == pytest.approx(2080 / 1.05)


def test_invalid_turning_proportion_rejected():
    with pytest.raises(ValueError):
        rr67_result({"turning_proportion": 1.1})
