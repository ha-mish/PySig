import pytest
from traffic_model.rr67 import saturation_flow


def test_rr67_base():
    assert saturation_flow({"method": "rr67_unopposed"}) == pytest.approx(2080)


def test_rr67_nearside():
    assert saturation_flow(
        {"method": "rr67_unopposed", "is_nearside_lane": True}
    ) == pytest.approx(1940)
