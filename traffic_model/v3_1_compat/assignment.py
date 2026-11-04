from dataclasses import dataclass
from math import exp
from .engine import simulate
class DemandConservationError(RuntimeError):pass
@dataclass(frozen=True,slots=True)
class AssignmentIteration: iteration:int;relative_gap:float;maximum_flow_change:float;conservation_error:float;converged:bool
@dataclass(frozen=True,slots=True)
class AssignmentResult: route_flows:dict;movement_flows:dict;simulation:object;iterations:tuple;converged:bool;maximum_conservation_error:float
def _audit(model,flows):
 error=0
 for pair,demand in model.od.items():
  assigned=sum(flows[r.route_id] for r in model.routes.values() if (r.origin_zone_id,r.destination_zone_id)==pair);error=max(error,abs(assigned-demand))
  if abs(assigned-demand)>model.assignment.conservation_tolerance:raise DemandConservationError(f'OD {pair}: matrix={demand}, assigned={assigned}')
 return error
def assign(model,controller=None,initial=None,progress=None):
 flows={r:0 for r in model.routes};flows.update(initial or {});delays={m:0 for m in model.movements};hist=[]
 for it in range(1,model.assignment.max_iterations+1):
  target={r:0 for r in model.routes};short=experienced=0
  for pair,demand in model.od.items():
   rs=[r for r in model.routes.values() if (r.origin_zone_id,r.destination_zone_id)==pair]
   if demand and not rs:raise ValueError(f'No route for {pair}')
   costs={r.route_id:sum(model.movements[m].free_flow_time_s+delays[m] for m in r.movement_ids) for r in rs};base=min(costs.values()) if costs else 0;ws={r:exp(-.08*(c-base)) for r,c in costs.items()};den=sum(ws.values()) or 1
   for r,v in ws.items():target[r]=demand*v/den
   short+=demand*base;experienced+=demand*sum(ws[r]/den*costs[r] for r in ws)
  step=1/it;new={r:flows[r]+step*(target[r]-flows[r]) for r in flows};change=max((abs(new[r]-flows[r]) for r in flows),default=0);flows=new;error=_audit(model,flows);mf={m:0 for m in model.movements}
  for rid,f in flows.items():
   for m in model.routes[rid].movement_ids:mf[m]+=f
  sim=simulate(model,mf,controller);delays={m:x.mean_delay_s for m,x in sim.movements.items()};gap=max(0,(experienced-short)/experienced) if experienced else 0;done=it>1 and change<=model.assignment.max_flow_change_tolerance;row=AssignmentIteration(it,gap,change,error,done);hist.append(row)
  if progress:progress(row)
  if done:break
 return AssignmentResult(flows,mf,sim,tuple(hist),hist[-1].converged,max(x.conservation_error for x in hist))
