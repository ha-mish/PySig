import pytest
from traffic_model.v3_1_compat.engine import State, _step


def test_queue_growth():
    s = State()
    _step(s, 2, 1, 10, 100)
    assert s.q == pytest.approx(10)
    assert s.delay == pytest.approx(50)


def test_queue_clearance():
    s = State(q=10)
    _step(s, 1, 2, 20, 100)
    assert s.q == pytest.approx(0)
    assert s.delay == pytest.approx(50)
