import pytest
from traffic_model.level_of_service import signalized_level_of_service


@pytest.mark.parametrize(
    ("delay", "grade"),
    [(10, "A"), (10.01, "B"), (20, "B"), (35, "C"), (55, "D"), (80, "E"), (80.01, "F")],
)
def test_los_boundaries(delay, grade):
    result = signalized_level_of_service(delay)
    assert result.grade == grade
    assert result.status == "screening"
