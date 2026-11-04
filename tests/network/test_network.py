from pathlib import Path
import pytest
from traffic_model.loader import load_model
from traffic_model.assignment import assign
from traffic_model.simulation import green
M=load_model(Path(__file__).parents[2]/'configs'/'example_network_optimisation.yaml')
def test_two_intersections():assert len(M.intersections)==2
def test_fixed_od_conserved():
 r=assign(M);assert sum(r.route_flows.values())==pytest.approx(700,abs=1e-6);assert r.iterations[-1].conservation_error<=1e-6
def test_link_travel_time_and_storage():
 r=assign(M);assert r.simulation.links['LINK_MAIN'].travel_time_s==pytest.approx(30);assert r.simulation.maximum_link_storage_utilisation<=1
def test_offset_changes_signal_state():
 c=M.controllers['C2'];assert green(c,'SG2_MAIN',0)!=green(c,'SG2_MAIN',25)
def test_routes_cross_intersections():
 r=M.routes['R_MAIN'];assert [M.movements[x].intersection_id for x in r.movement_ids]==['I1','I2']
