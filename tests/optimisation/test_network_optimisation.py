from pathlib import Path
from dataclasses import replace
from traffic_model.loader import load_model
from traffic_model.optimisation import optimise,plans
M=load_model(Path(__file__).parents[2]/'configs'/'example_network_optimisation.yaml')
def test_controller_candidates_include_offsets_and_splits():
 p=list(plans(M.controllers['C1'],limit=16));assert len({x.offset_s for x in p})>1;assert len({tuple(y.duration_s for y in x.phases) for x in p})>1
def test_network_optimisation_evaluates_both_controllers():
 r=optimise(M);assert {x.controller_id for x in r.candidates}=={'C1','C2'};assert r.best_assignment.iterations[-1].conservation_error<=1e-6
def test_fixed_controller_is_not_optimised():
 cs=dict(M.controllers);cs['C2']=replace(cs['C2'],optimisation_enabled=False);m=replace(M,controllers=cs);r=optimise(m);assert {x.controller_id for x in r.candidates}=={'C1'}
