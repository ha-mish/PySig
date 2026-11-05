from dataclasses import dataclass, replace
from itertools import product
from .assignment import assign


@dataclass(frozen=True, slots=True)
class Candidate:
    outer_iteration: int
    controller_id: str
    candidate: int
    cycle_time_s: float
    offset_s: float
    phase_durations_s: tuple
    network_delay_pcu_hours: float
    maximum_lane_storage_utilisation: float
    maximum_link_storage_utilisation: float
    assignment_converged: bool
    assignment_iterations: int
    od_conservation_error: float
    feasible: bool


@dataclass(frozen=True, slots=True)
class Result:
    controllers: dict
    best_assignment: object
    candidates: tuple
    outer_iterations: int
    signal_plans_stable: bool
    route_flows_stable: bool
    converged: bool


def plans(c, common=None, limit=100):
    cycles = common or c.cycle_candidates or (c.cycle_time_s,)
    n = 0
    for cycle in cycles:
        available = cycle - sum(p.intergreen_after_s for p in c.phases)
        vals = [
            c.minimum_green_s + i * c.split_step_s
            for i in range(
                max(
                    1,
                    int(
                        (available - len(c.phases) * c.minimum_green_s) / c.split_step_s
                    )
                    + 1,
                )
            )
        ]
        for split in product(vals, repeat=len(c.phases)):
            if abs(sum(split) - available) > 1e-6:
                continue
            offsets = (
                [
                    i * c.offset_step_s
                    for i in range(max(1, int(cycle / c.offset_step_s)))
                ]
                if c.offset_step_s > 0
                else [c.offset_s]
            )
            for off in offsets:
                n += 1
                if n > limit:
                    return
                yield replace(
                    c,
                    cycle_time_s=cycle,
                    offset_s=off,
                    phases=tuple(
                        replace(p, duration_s=d) for p, d in zip(c.phases, split)
                    ),
                )


def optimise(model, progress=None):
    current = dict(model.controllers)
    prior = None
    lastsig = None
    rows = []
    stable = flowstable = False
    final = None
    targets = [c for c in current.values() if c.optimisation_enabled]
    if not targets:
        a = assign(model, current)
        return Result(current, a, (), 1, True, True, a.converged)
    for outer in range(1, model.optimisation.outer_iterations + 1):
        for base in targets:
            best = None
            common = (
                model.optimisation.common_cycle_candidates
                if model.optimisation.common_cycle
                else None
            )
            for i, candidate in enumerate(
                plans(
                    current[base.controller_id],
                    common,
                    model.optimisation.max_candidates_per_controller,
                ),
                1,
            ):
                cs = dict(current)
                cs[base.controller_id] = candidate
                a = assign(model, cs, prior)
                s = a.simulation
                q = (
                    s.maximum_lane_storage_utilisation
                    <= model.optimisation.max_lane_storage_utilisation
                    and s.maximum_link_storage_utilisation
                    <= model.optimisation.max_link_storage_utilisation
                )
                conv = (
                    a.converged
                    or model.optimisation.unconverged_candidate_policy == "allow"
                )
                feasible = q and conv
                row = Candidate(
                    outer,
                    base.controller_id,
                    i,
                    candidate.cycle_time_s,
                    candidate.offset_s,
                    tuple(p.duration_s for p in candidate.phases),
                    s.network_delay_pcu_hours,
                    s.maximum_lane_storage_utilisation,
                    s.maximum_link_storage_utilisation,
                    a.converged,
                    len(a.iterations),
                    a.iterations[-1].conservation_error if a.iterations else 0.0,
                    feasible,
                )
                rows.append(row)
                if progress:
                    progress(row)
                if feasible and (
                    best is None
                    or row.network_delay_pcu_hours < best[0].network_delay_pcu_hours
                ):
                    best = (row, candidate, a)
            if best is None:
                raise ValueError(f"No feasible plan for {base.controller_id}")
            current[base.controller_id] = best[1]
            prior = best[2].route_flows
        signature = tuple(
            (k, v.cycle_time_s, v.offset_s, tuple(p.duration_s for p in v.phases))
            for k, v in sorted(current.items())
        )
        stable = signature == lastsig
        final = assign(model, current, prior)
        flowstable = (
            prior is not None
            and max(
                (
                    abs(final.route_flows[r] - prior.get(r, 0))
                    for r in final.route_flows
                ),
                default=0,
            )
            <= model.optimisation.outer_flow_tolerance
        )
        prior = final.route_flows
        lastsig = signature
        if stable and flowstable:
            return Result(current, final, tuple(rows), outer, True, True, True)
    return Result(current, final, tuple(rows), outer, stable, flowstable, False)
