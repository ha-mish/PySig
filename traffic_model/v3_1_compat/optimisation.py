from dataclasses import dataclass,replace
from itertools import product
from .domain import Controller
from .assignment import assign
@dataclass(frozen=True,slots=True)
class CandidateResult:
 outer_iteration:int;candidate:int;cycle_time_s:float;offset_s:float;phase_durations_s:tuple;objective:str;objective_value:float;total_delay_pcu_hours:float;prc_percent:float;maximum_storage_utilisation:float;queue_constraint_pass:bool;assignment_converged:bool;assignment_iterations:int;assignment_relative_gap:float;assignment_maximum_flow_change:float;od_conservation_pass:bool;maximum_conservation_error:float;feasible:bool
@dataclass(frozen=True,slots=True)
class OptimisationResult: best:CandidateResult;best_controller:Controller;candidates:tuple;outer_iterations:int;signal_plan_stable:bool;route_flows_stable:bool;converged:bool
def _splits(cycle,phases,step,minimum):
 available=cycle-sum(p.intergreen_after_s for p in phases);n=len(phases);vals=[minimum+i*step for i in range(int((available-n*minimum)/step)+1)];return [x for x in product(vals,repeat=n) if abs(sum(x)-available)<1e-6]
def controllers(model):
 o=model.optimisation;count=0
 for cycle in o.cycle_times_s:
  for split in _splits(cycle,model.controller.phases,o.split_step_s,o.minimum_phase_green_s):
   offsets=[i*o.offset_step_s for i in range(max(1,int(cycle/o.offset_step_s)))] if o.offset_step_s>0 else [0]
   for offset in offsets:
    count+=1
    if count>o.maximum_candidates:return
    yield Controller(model.controller.controller_id,cycle,offset,tuple(replace(p,duration_s=d) for p,d in zip(model.controller.phases,split)))
def optimise(model,progress=None):
 prior=None;allrows=[];lastplan=None;route_stable=False;plan_stable=False
 for outer in range(1,model.optimisation.outer_iterations+1):
  best=None;bestctl=None;besta=None
  for i,ctl in enumerate(controllers(model),1):
   a=assign(model,ctl,prior);s=a.simulation;qpass=s.maximum_storage_utilisation<=model.optimisation.queue_storage_utilisation_limit+1e-12;cp=a.converged or model.optimisation.unconverged_candidate_policy=='allow';feasible=qpass and cp and a.maximum_conservation_error<=model.assignment.conservation_tolerance;value=(-s.prc_percent if model.optimisation.objective=='prc' else s.total_delay_pcu_hours) if feasible else float('inf');last=a.iterations[-1];row=CandidateResult(outer,i,ctl.cycle_time_s,ctl.offset_s,tuple(p.duration_s for p in ctl.phases),model.optimisation.objective,value,s.total_delay_pcu_hours,s.prc_percent,s.maximum_storage_utilisation,qpass,a.converged,len(a.iterations),last.relative_gap,last.maximum_flow_change,a.maximum_conservation_error<=model.assignment.conservation_tolerance,a.maximum_conservation_error,feasible);allrows.append(row)
   if progress:progress(row)
   if feasible and (best is None or value<best.objective_value):best,bestctl,besta=row,ctl,a
  if best is None:raise ValueError('No feasible candidate: check assignment convergence and queue-storage constraints')
  plan=(bestctl.cycle_time_s,bestctl.offset_s,tuple(p.duration_s for p in bestctl.phases));plan_stable=plan==lastplan
  route_stable=prior is not None and max((abs(besta.route_flows[r]-prior.get(r,0)) for r in besta.route_flows),default=0)<=model.optimisation.outer_flow_tolerance
  prior=besta.route_flows;lastplan=plan
  if plan_stable and route_stable:return OptimisationResult(best,bestctl,tuple(allrows),outer,True,True,True)
 return OptimisationResult(best,bestctl,tuple(allrows),outer,plan_stable,route_stable,False)
