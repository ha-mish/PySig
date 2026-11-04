from pathlib import Path
import pytest
from traffic_model.loader import load_model
from traffic_model.validation import validate
from traffic_model.rr67 import saturation_flow
from traffic_model.assignment import assign
ROOT=Path(__file__).resolve().parents[1]
def test_rr67_base():assert saturation_flow({'method':'rr67_unopposed'})==pytest.approx(2080)
def test_rr67_nearside():assert saturation_flow({'method':'rr67_unopposed','is_nearside_lane':True})==pytest.approx(1940)
def test_example_valid():assert validate(load_model(ROOT/'configs'/'example_intersection_optimisation.yaml'))==[]
def test_fixed_od_conserved():
 m=load_model(ROOT/'configs'/'example_intersection_optimisation.yaml');a=assign(m);assert sum(a.route_flows.values())==pytest.approx(sum(m.od.values()),abs=1e-6);assert a.iterations[-1].conservation_error<=1e-6
