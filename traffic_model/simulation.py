from dataclasses import dataclass
from math import ceil
from .rr67 import saturation_flow, capacity_method


@dataclass(frozen=True, slots=True)
class MovementResult:
    movement_id: str
    intersection_id: str
    lane_id: str
    to_lane_id: str | None
    signal_group_id: str
    movement_type: str
    demand_pcu_per_hour: float
    saturation_flow_pcu_per_hour: float
    capacity_pcu_per_hour: float
    effective_green_s: float
    effective_green_ratio: float
    arrivals_pcu: float
    departures_pcu: float
    final_queue_pcu: float
    maximum_queue_pcu: float
    maximum_queue_m: float
    total_delay_pcu_hours: float
    mean_delay_seconds_per_pcu: float
    degree_of_saturation: float
    unserved_demand_pcu: float
    storage_overflow_pcu: float
    storage_full_seconds: float
    capacity_method: str


@dataclass(frozen=True, slots=True)
class LaneResult:
    lane_id: str
    intersection_id: str
    movement_ids: tuple[str, ...]
    demand_pcu_per_hour: float
    saturation_flow_pcu_per_hour: float
    capacity_pcu_per_hour: float
    arrivals_pcu: float
    departures_pcu: float
    final_queue_pcu: float
    maximum_queue_pcu: float
    maximum_queue_m: float
    total_delay_pcu_hours: float
    mean_delay_seconds_per_pcu: float
    degree_of_saturation: float
    unserved_demand_pcu: float
    storage_pcu: float
    storage_utilisation: float
    storage_overflow_pcu: float
    storage_full_seconds: float
    capacity_method: str


@dataclass(frozen=True, slots=True)
class LinkResult:
    link_id: str
    travel_time_s: float
    flow_pcu_per_hour: float
    maximum_storage_pcu: float
    maximum_storage_utilisation: float
    spillback_seconds: float


@dataclass(frozen=True, slots=True)
class SimulationResult:
    movements: dict
    lanes: dict
    links: dict
    network_delay_pcu_hours: float
    maximum_lane_storage_utilisation: float
    maximum_link_storage_utilisation: float
    movement_delay_s: dict
    throughput_pcu: float


def green(controller, signal_group_id, time_s):
    local = (time_s - controller.offset_s) % controller.cycle_time_s
    cursor = 0.0
    for phase in controller.phases:
        if cursor <= local < cursor + phase.duration_s:
            return signal_group_id in phase.active_signal_groups
        cursor += phase.duration_s + phase.intergreen_after_s
    return False


def green_seconds(controller, signal_group_id):
    return sum(
        phase.duration_s
        for phase in controller.phases
        if signal_group_id in phase.active_signal_groups
    )


def _proportional_allocation(total, weights):
    """Allocate a non-negative total proportionally, preserving the total."""
    weight_sum = sum(max(0.0, value) for value in weights.values())
    if total <= 0 or weight_sum <= 0:
        return {key: 0.0 for key in weights}
    return {key: total * max(0.0, value) / weight_sum for key, value in weights.items()}


def simulate(model, movement_flows, controllers=None):
    """Run a time-sliced, lane-queue simulation.

    Version 4.2.2 stores one physical queue and one storage constraint per lane.
    Movement subqueues retain composition within that lane. A lane's saturation
    flow is applied once per time slice and shared by eligible movements.

    When movements on a shared lane have different signal permissions, a simple
    FIFO blocking factor is used: the available lane service is multiplied by
    the proportion of the lane queue belonging to currently permitted
    movements. This prevents a red movement from being ignored while avoiding
    duplicate lane capacity.
    """
    cs = controllers or model.controllers
    dt = model.network.time_slice_s
    steps = max(1, int(model.network.horizon_s / dt))

    movements_by_lane = {lane_id: [] for lane_id in model.lanes}
    for movement_id, movement in model.movements.items():
        movements_by_lane.setdefault(movement.from_lane_id, []).append(movement_id)

    # Movement composition within shared physical lane queues.
    movement_queue = {mid: 0.0 for mid in model.movements}
    movement_arrived = {mid: 0.0 for mid in model.movements}
    movement_departed = {mid: 0.0 for mid in model.movements}
    movement_delay = {mid: 0.0 for mid in model.movements}
    movement_max_queue = {mid: 0.0 for mid in model.movements}
    movement_overflow = {mid: 0.0 for mid in model.movements}
    movement_full_time = {mid: 0.0 for mid in model.movements}
    movement_service_capacity = {mid: 0.0 for mid in model.movements}

    lane_arrived = {lid: 0.0 for lid in model.lanes}
    lane_departed = {lid: 0.0 for lid in model.lanes}
    lane_delay = {lid: 0.0 for lid in model.lanes}
    lane_max_queue = {lid: 0.0 for lid in model.lanes}
    lane_overflow = {lid: 0.0 for lid in model.lanes}
    lane_full_time = {lid: 0.0 for lid in model.lanes}
    lane_service_capacity = {lid: 0.0 for lid in model.lanes}

    scheduled_arrivals = {
        mid: [movement_flows.get(mid, 0.0) / 3600.0 * dt for _ in range(steps)]
        for mid in model.movements
    }

    link_store = {lid: 0.0 for lid in model.links}
    link_max = {lid: 0.0 for lid in model.links}
    link_spillback = {lid: 0.0 for lid in model.links}
    link_flow = {lid: 0.0 for lid in model.links}
    link_by_upstream = {link.upstream_movement_id: link for link in model.links.values()}
    throughput = 0.0

    for step in range(steps):
        time_s = step * dt

        for lane_id, lane in model.lanes.items():
            mids = movements_by_lane.get(lane_id, [])
            if not mids:
                continue

            # 1. Add all movement arrivals to one shared physical lane storage.
            incoming = {mid: scheduled_arrivals[mid][step] for mid in mids}
            incoming_total = sum(incoming.values())
            lane_arrived[lane_id] += incoming_total
            for mid, value in incoming.items():
                movement_arrived[mid] += value

            lane_queue_before = sum(movement_queue[mid] for mid in mids)
            available_storage = max(0.0, lane.storage_pcu - lane_queue_before)
            accepted_total = min(available_storage, incoming_total)
            accepted = _proportional_allocation(accepted_total, incoming)
            for mid in mids:
                movement_queue[mid] += accepted[mid]
                rejected = incoming[mid] - accepted[mid]
                movement_overflow[mid] += rejected
                lane_overflow[lane_id] += rejected

            lane_queue = sum(movement_queue[mid] for mid in mids)
            if lane_queue >= lane.storage_pcu - 1e-9:
                lane_full_time[lane_id] += dt
                for mid in mids:
                    if movement_queue[mid] > 0:
                        movement_full_time[mid] += dt

            # 2. Apply lane capacity once, shared across permitted movements.
            intersection_id = model.movements[mids[0]].intersection_id
            controller = cs[model.intersections[intersection_id].controller_id]
            permitted = {
                mid: green(controller, model.movements[mid].signal_group_id, time_s)
                for mid in mids
            }
            eligible_queue = {
                mid: movement_queue[mid] if permitted[mid] else 0.0
                for mid in mids
            }
            eligible_total = sum(eligible_queue.values())
            saturation = saturation_flow(lane.saturation_flow)
            raw_capacity_step = saturation / 3600.0 * dt

            # FIFO blocking: red traffic within the shared queue reduces usable
            # green capacity in proportion to its share of the physical queue.
            blocking_factor = eligible_total / lane_queue if lane_queue > 1e-12 else 0.0
            usable_capacity_step = raw_capacity_step * blocking_factor
            service_alloc = _proportional_allocation(usable_capacity_step, eligible_queue)
            lane_service_capacity[lane_id] += usable_capacity_step

            for mid in mids:
                movement_service_capacity[mid] += service_alloc[mid]
                desired_departure = min(movement_queue[mid], service_alloc[mid])
                actual_departure = desired_departure
                link = link_by_upstream.get(mid)

                if link:
                    receiving = max(0.0, link.storage_pcu - link_store[link.link_id])
                    actual_departure = min(desired_departure, receiving)
                    link_store[link.link_id] += actual_departure
                    link_flow[link.link_id] += actual_departure
                    if receiving <= 1e-9:
                        link_spillback[link.link_id] += dt

                    travel_steps = max(
                        1,
                        int(ceil((link.length_m / (link.speed_kmh / 3.6)) / dt)),
                    )
                    arrival_step = step + travel_steps
                    if arrival_step < steps:
                        release = link_store[link.link_id] * (
                            1.0 - min(0.95, max(0.0, link.dispersion))
                        )
                        scheduled_arrivals[link.downstream_movement_id][arrival_step] += release
                        link_store[link.link_id] -= release
                else:
                    throughput += actual_departure

                movement_queue[mid] -= actual_departure
                movement_departed[mid] += actual_departure
                lane_departed[lane_id] += actual_departure

            # 3. One physical lane delay, partitioned to movement composition.
            lane_queue_after = sum(movement_queue[mid] for mid in mids)
            lane_delay_increment = lane_queue_after * dt
            lane_delay[lane_id] += lane_delay_increment
            composition = _proportional_allocation(lane_delay_increment, {
                mid: movement_queue[mid] for mid in mids
            })
            for mid in mids:
                movement_delay[mid] += composition[mid]
                movement_max_queue[mid] = max(
                    movement_max_queue[mid], movement_queue[mid]
                )
            lane_max_queue[lane_id] = max(lane_max_queue[lane_id], lane_queue_after)

        for link_id in link_store:
            link_max[link_id] = max(link_max[link_id], link_store[link_id])

    movement_results = {}
    lane_results = {}
    maximum_lane_utilisation = 0.0

    for lane_id, lane in model.lanes.items():
        mids = movements_by_lane.get(lane_id, [])
        if not mids:
            continue
        demand = sum(movement_flows.get(mid, 0.0) for mid in mids)
        capacity = lane_service_capacity[lane_id] / model.network.horizon_s * 3600.0
        degree = demand / capacity if capacity > 0 else (999.0 if demand > 0 else 0.0)
        final_queue = sum(movement_queue[mid] for mid in mids)
        maximum_queue = lane_max_queue[lane_id]
        utilisation = maximum_queue / lane.storage_pcu if lane.storage_pcu else 0.0
        maximum_lane_utilisation = max(maximum_lane_utilisation, utilisation)
        lane_results[lane_id] = LaneResult(
            lane_id=lane_id,
            intersection_id=lane.intersection_id,
            movement_ids=tuple(mids),
            demand_pcu_per_hour=demand,
            saturation_flow_pcu_per_hour=saturation_flow(lane.saturation_flow),
            capacity_pcu_per_hour=capacity,
            arrivals_pcu=lane_arrived[lane_id],
            departures_pcu=lane_departed[lane_id],
            final_queue_pcu=final_queue,
            maximum_queue_pcu=maximum_queue,
            maximum_queue_m=maximum_queue * model.pcu_length_m,
            total_delay_pcu_hours=lane_delay[lane_id] / 3600.0,
            mean_delay_seconds_per_pcu=(
                lane_delay[lane_id] / lane_departed[lane_id]
                if lane_departed[lane_id] > 0 else 0.0
            ),
            degree_of_saturation=degree,
            unserved_demand_pcu=max(0.0, lane_arrived[lane_id] - lane_departed[lane_id]),
            storage_pcu=lane.storage_pcu,
            storage_utilisation=utilisation,
            storage_overflow_pcu=lane_overflow[lane_id],
            storage_full_seconds=lane_full_time[lane_id],
            capacity_method=capacity_method(lane.saturation_flow),
        )

        for mid in mids:
            movement = model.movements[mid]
            controller = cs[model.intersections[movement.intersection_id].controller_id]
            effective_green = green_seconds(controller, movement.signal_group_id)
            movement_capacity = (
                movement_service_capacity[mid] / model.network.horizon_s * 3600.0
            )
            movement_demand = movement_flows.get(mid, 0.0)
            movement_results[mid] = MovementResult(
                movement_id=mid,
                intersection_id=movement.intersection_id,
                lane_id=lane_id,
                to_lane_id=movement.to_lane_id,
                signal_group_id=movement.signal_group_id,
                movement_type=movement.movement_type,
                demand_pcu_per_hour=movement_demand,
                saturation_flow_pcu_per_hour=saturation_flow(lane.saturation_flow),
                capacity_pcu_per_hour=movement_capacity,
                effective_green_s=effective_green,
                effective_green_ratio=(
                    effective_green / controller.cycle_time_s
                    if controller.cycle_time_s else 0.0
                ),
                arrivals_pcu=movement_arrived[mid],
                departures_pcu=movement_departed[mid],
                final_queue_pcu=movement_queue[mid],
                maximum_queue_pcu=movement_max_queue[mid],
                maximum_queue_m=movement_max_queue[mid] * model.pcu_length_m,
                total_delay_pcu_hours=movement_delay[mid] / 3600.0,
                mean_delay_seconds_per_pcu=(
                    movement_delay[mid] / movement_departed[mid]
                    if movement_departed[mid] > 0 else 0.0
                ),
                degree_of_saturation=(
                    movement_demand / movement_capacity
                    if movement_capacity > 0 else (999.0 if movement_demand > 0 else 0.0)
                ),
                unserved_demand_pcu=max(
                    0.0, movement_arrived[mid] - movement_departed[mid]
                ),
                storage_overflow_pcu=movement_overflow[mid],
                storage_full_seconds=movement_full_time[mid],
                capacity_method=capacity_method(lane.saturation_flow),
            )

    link_results = {
        link_id: LinkResult(
            link_id=link_id,
            travel_time_s=link.length_m / (link.speed_kmh / 3.6),
            flow_pcu_per_hour=(
                link_flow[link_id] / model.network.horizon_s * 3600.0
                if model.network.horizon_s else 0.0
            ),
            maximum_storage_pcu=link_max[link_id],
            maximum_storage_utilisation=(
                link_max[link_id] / link.storage_pcu if link.storage_pcu else 0.0
            ),
            spillback_seconds=link_spillback[link_id],
        )
        for link_id, link in model.links.items()
    }
    maximum_link_utilisation = max(
        (row.maximum_storage_utilisation for row in link_results.values()),
        default=0.0,
    )
    movement_mean_delay = {
        mid: result.mean_delay_seconds_per_pcu
        for mid, result in movement_results.items()
    }
    return SimulationResult(
        movements=movement_results,
        lanes=lane_results,
        links=link_results,
        network_delay_pcu_hours=sum(
            row.total_delay_pcu_hours for row in lane_results.values()
        ),
        maximum_lane_storage_utilisation=maximum_lane_utilisation,
        maximum_link_storage_utilisation=maximum_link_utilisation,
        movement_delay_s=movement_mean_delay,
        throughput_pcu=throughput,
    )
