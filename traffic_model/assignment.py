from dataclasses import dataclass
from math import exp
from .simulation import simulate


class DemandConservationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Iteration:
    iteration: int
    maximum_flow_change: float
    conservation_error: float
    converged: bool


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    route_flows: dict
    movement_flows: dict
    simulation: object
    iterations: tuple
    converged: bool


def audit(model, flows):
    e = 0.0
    for od, q in model.od.items():
        a = sum(
            flows[r.route_id]
            for r in model.routes.values()
            if (r.origin_zone_id, r.destination_zone_id) == od
        )
        e = max(e, abs(a - q))
        if abs(a - q) > model.assignment.conservation_tolerance:
            raise DemandConservationError(f"{od}: matrix={q}, assigned={a}")
    return e


def assign(model, controllers=None, initial=None):
    flows = {r: 0.0 for r in model.routes}
    flows.update(initial or {})
    cost = {
        r: sum(model.movements[m].free_flow_time_s for m in x.movement_ids)
        for r, x in model.routes.items()
    }
    hist = []
    for it in range(1, model.assignment.max_iterations + 1):
        target = {r: 0.0 for r in flows}
        for od, q in model.od.items():
            rs = [
                r
                for r in model.routes.values()
                if (r.origin_zone_id, r.destination_zone_id) == od
            ]
            if q > 0 and not rs:
                raise ValueError(f"No route for OD pair {od}")
            if not rs:
                continue
            base = min(cost[r.route_id] for r in rs)
            ws = {
                r.route_id: exp(-model.assignment.theta * (cost[r.route_id] - base))
                for r in rs
            }
            den = sum(ws.values()) or 1
            for r, v in ws.items():
                target[r] = q * v / den
        step = 1 / it
        new = {r: flows[r] + step * (target[r] - flows[r]) for r in flows}
        change = max((abs(new[r] - flows[r]) for r in flows), default=0.0)
        flows = new
        e = audit(model, flows)
        mf = {m: 0.0 for m in model.movements}
        for rid, q in flows.items():
            for m in model.routes[rid].movement_ids:
                mf[m] += q
        sim = simulate(model, mf, controllers)
        cost = {
            rid: sum(
                model.movements[m].free_flow_time_s + sim.movement_delay_s[m]
                for m in r.movement_ids
            )
            for rid, r in model.routes.items()
        }
        done = it > 1 and change <= model.assignment.max_flow_change_tolerance
        hist.append(Iteration(it, change, e, done))
        if done:
            break
    return AssignmentResult(
        flows, mf, sim, tuple(hist), hist[-1].converged if hist else True
    )
