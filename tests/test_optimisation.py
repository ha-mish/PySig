from pathlib import Path
from traffic_model.loader import load_model
from traffic_model.optimisation import optimise

ROOT = Path(__file__).resolve().parents[1]


def test_single_intersection_optimisation():
    m = load_model(ROOT / "configs" / "example_intersection_optimisation.yaml")
    r = optimise(m)
    assert r.best_assignment is not None
    assert r.best_assignment.iterations[-1].conservation_error <= 1e-6


def test_network_optimisation():
    m = load_model(ROOT / "configs" / "example_network_optimisation.yaml")
    r = optimise(m)
    assert set(r.controllers) == {"C1", "C2"}
    assert r.best_assignment.iterations[-1].conservation_error <= 1e-6
