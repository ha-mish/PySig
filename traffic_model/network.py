from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LinkResult:
    link_id: str
    travel_time_s: float
    flow_pcu_per_hour: float
    receiving_capacity_pcu: float


@dataclass(frozen=True, slots=True)
class NetworkResult:
    links: dict
    movement_flows: dict
    mean_route_costs: dict
    maximum_link_storage_utilisation: float


def free_flow_time(link):
    return link.length_m / (link.speed_kmh / 3.6)


def propagate(model, movement_flows):
    links = {}
    maxu = 0
    cost = {}
    for lid, l in model.links.items():
        flow = movement_flows.get(l.upstream_movement_id, 0)
        tt = free_flow_time(l)
        queued = max(0, (flow - 1800) * model.network.horizon_s / 3600)
        u = min(1, queued / l.storage_pcu if l.storage_pcu else 0)
        maxu = max(maxu, u)
        links[lid] = LinkResult(lid, tt, flow, max(0, l.storage_pcu - queued))
    for rid, r in model.routes.items():
        c = sum(model.movements[m].free_flow_time_s for m in r.movement_ids)
        for link in model.links.values():
            if (
                link.upstream_movement_id in r.movement_ids
                and link.downstream_movement_id in r.movement_ids
            ):
                c += free_flow_time(l)
        cost[rid] = c
    return NetworkResult(links, movement_flows, cost, maxu)
