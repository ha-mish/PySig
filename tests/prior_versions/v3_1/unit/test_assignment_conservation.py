from pathlib import Path
import pytest
from traffic_model.v3_1_compat.loader import load_model
from traffic_model.v3_1_compat.assignment import assign
M=load_model(Path(__file__).parents[2]/'configs'/'example_optimisation.yaml')
def test_each_od_total_is_fixed():
 r=assign(M)
 for pair,demand in M.od.items():
  assigned=sum(r.route_flows[x.route_id] for x in M.routes.values() if (x.origin_zone_id,x.destination_zone_id)==pair)
  assert assigned==pytest.approx(demand,abs=1e-6)
def test_assignment_reports_convergence_and_conservation():
 r=assign(M);assert r.converged;assert r.maximum_conservation_error<=M.assignment.conservation_tolerance
