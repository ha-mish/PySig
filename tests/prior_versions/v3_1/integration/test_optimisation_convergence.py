from pathlib import Path
from traffic_model.v3_1_compat.loader import load_model
from traffic_model.v3_1_compat.optimisation import optimise
M=load_model(Path(__file__).parents[2]/'configs'/'example_optimisation.yaml')
def test_every_feasible_candidate_has_converged_assignment_and_conserved_od():
 r=optimise(M)
 assert all(x.assignment_converged and x.od_conservation_pass for x in r.candidates if x.feasible)
 assert r.best.assignment_converged and r.best.od_conservation_pass
def test_outer_convergence_is_explicit():
 r=optimise(M);assert isinstance(r.signal_plan_stable,bool);assert isinstance(r.route_flows_stable,bool)
