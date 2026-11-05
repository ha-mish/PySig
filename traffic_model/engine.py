from dataclasses import dataclass
from .rr67 import saturation_flow


@dataclass(slots=True)
class State:
    q: float = 0
    arr: float = 0
    dep: float = 0
    delay: float = 0
    qmax: float = 0


@dataclass(frozen=True, slots=True)
class MovementResult:
    movement_id: str
    demand: float
    capacity: float
    degree_of_saturation: float
    mean_delay_s: float
    maximum_queue_pcu: float
    storage_pcu: float


@dataclass(frozen=True, slots=True)
class SimulationResult:
    movements: dict
    total_delay_pcu_hours: float
    maximum_storage_utilisation: float
    prc_percent: float


def _step(s, a, c, dt, storage):
    left = dt
    while left > 1e-10:
        q = s.q
        h = left
        if q > 0 and c > a:
            h = min(h, q / (c - a))
        if q < storage and a > c:
            h = min(h, (storage - q) / (a - c))
        accepted = a if q < storage - 1e-9 or a <= c else c
        dep = accepted if q <= 1e-9 and c > accepted else c
        q1 = max(0, min(storage, q + (accepted - dep) * h))
        s.arr += accepted * h
        s.dep += dep * h
        s.delay += (q + q1) * h / 2
        s.q = q1
        s.qmax = max(s.qmax, q1)
        left -= h
        if h <= 1e-12:
            break


def simulate(model, demands, controller=None):
    ctl = controller or model.controller
    t = 0
    spans = []
    for p in ctl.phases:
        gs = t + model.start_displacement_s
        ge = t + max(
            model.start_displacement_s, p.duration_s - model.end_displacement_s
        )
        spans.append((t, t + p.duration_s, gs, ge, set(p.active_signal_groups)))
        t += p.duration_s + p.intergreen_after_s
    states = {m: State() for m in model.movements}
    sats = {
        m: saturation_flow(model.lanes[x.from_lane_id].saturation_flow)
        for m, x in model.movements.items()
    }
    conf = {x.yielding_movement_id: x for x in model.conflicts}
    for cyc in range(model.warm_up_cycles + model.reporting_cycles):
        if cyc == model.warm_up_cycles:
            states = {k: State(v.q, 0, 0, 0, v.q) for k, v in states.items()}
        for ps, pe, gs, ge, groups in spans:
            b = sorted({ps, gs, ge, pe})
            for x, y in zip(b, b[1:]):
                active = groups if gs <= (x + y) / 2 < ge else set()
                am = {
                    m.movement_id
                    for m in model.movements.values()
                    if m.signal_group_id in active
                }
                for mid, m in model.movements.items():
                    cap = sats[mid] / 3600 if mid in am else 0
                    cf = conf.get(mid)
                    if cf and any(z in am for z in cf.priority_movement_ids):
                        cap *= cf.active_capacity_factor
                    _step(
                        states[mid],
                        demands.get(mid, 0) / 3600,
                        cap,
                        y - x,
                        model.lanes[m.from_lane_id].storage_pcu,
                    )
    out = {}
    total = maxu = maxdos = 0
    for mid, s in states.items():
        m = model.movements[mid]
        green = sum(
            max(0, ge - gs) for _, _, gs, ge, g in spans if m.signal_group_id in g
        )
        cap = sats[mid] * green / ctl.cycle_time_s
        dos = (
            demands.get(mid, 0) / cap
            if cap
            else (999 if demands.get(mid, 0) > 0 else 0)
        )
        mean = s.delay / s.dep if s.dep else 0
        storage = model.lanes[m.from_lane_id].storage_pcu
        out[mid] = MovementResult(
            mid, demands.get(mid, 0), cap, dos, mean, s.qmax, storage
        )
        total += s.delay / 3600
        maxu = max(maxu, s.qmax / storage)
        maxdos = max(maxdos, dos)
    return SimulationResult(
        out,
        total,
        maxu,
        100 * (model.optimisation.prc_target_dos / maxdos - 1) if maxdos else 999,
    )
