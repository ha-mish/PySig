"""PySig 0.4.5a event-driven analytical shared-lane engine."""

from __future__ import annotations

from collections import defaultdict
from math import isinf

from ...conflicts import active_capacity_factor
from ...rr67 import capacity_method, saturation_flow
from ...timing import (
    green_time,
    nominal_capacity_pcu_per_hour,
    nominal_degree_of_saturation,
)
from ..results import AnalyticalLaneResult, AnalyticalMovementResult, AnalyticalResult
from .queue import solve_interval
from .shared_lane import front_blocking_state, movement_proportions
from .signals import service_intervals


class AnalyticalEngine:
    """Analytical fixed-time engine with expected front-blocking shared lanes.

    Differently controlled movements may share a lane. The engine assumes
    destination classes are independently mixed in the queue. When only a
    subset of movements has green, the expected number of eligible vehicles
    before the first red movement is p_green / p_red. The lane then blocks until
    a signal event changes eligibility.
    """

    def calculate(self, model, movement_flows, controllers=None):
        if model.links:
            raise ValueError(
                "PySig 0.4.5a analytical mode does not yet support network "
                "links. Use simulation pending the 0.4.5b link/spillback engine."
            )

        controllers = controllers or model.controllers
        movements_by_lane = defaultdict(list)
        for movement_id, movement in model.movements.items():
            movements_by_lane[movement.from_lane_id].append(movement_id)

        movement_results = {}
        lane_results = {}
        movement_delay_s = {}
        network_delay_hours = 0.0
        throughput = 0.0
        maximum_storage_utilisation = 0.0

        for lane_id, movement_ids in movements_by_lane.items():
            lane_result, lane_movements = self._solve_lane(
                model,
                lane_id,
                movement_ids,
                movement_flows,
                controllers,
            )
            lane_results[lane_id] = lane_result
            movement_results.update(lane_movements)
            movement_delay_s.update(
                {
                    movement_id: result.mean_delay_seconds_per_pcu
                    for movement_id, result in lane_movements.items()
                }
            )
            network_delay_hours += lane_result.total_delay_pcu_hours
            throughput += lane_result.departures_pcu
            maximum_storage_utilisation = max(
                maximum_storage_utilisation,
                lane_result.storage_utilisation,
            )

        return AnalyticalResult(
            movements=movement_results,
            lanes=lane_results,
            links={},
            network_delay_pcu_hours=network_delay_hours,
            maximum_lane_storage_utilisation=maximum_storage_utilisation,
            maximum_link_storage_utilisation=0.0,
            movement_delay_s=movement_delay_s,
            throughput_pcu=throughput,
        )

    def _solve_lane(
        self,
        model,
        lane_id,
        movement_ids,
        movement_flows,
        controllers,
    ):
        lane = model.lanes[lane_id]
        movements = [model.movements[mid] for mid in movement_ids]
        intersection_id = movements[0].intersection_id
        controller = controllers[model.intersections[intersection_id].controller_id]
        horizon = model.network.horizon_s
        saturation = saturation_flow(lane.saturation_flow)
        signal_groups = tuple(sorted({m.signal_group_id for m in movements}))

        demand_by_movement = {
            mid: max(0.0, float(movement_flows.get(mid, 0.0))) for mid in movement_ids
        }
        demand_shares = movement_proportions(demand_by_movement, demand_by_movement)
        arrival_rates = {
            mid: value / 3600.0 for mid, value in demand_by_movement.items()
        }
        lane_demand = sum(demand_by_movement.values())

        service_by_movement = {
            mid: service_intervals(
                controller,
                model.movements[mid].signal_group_id,
                horizon,
                model.start_displacement_s,
                model.end_displacement_s,
            )
            for mid in movement_ids
        }
        priority_intervals = self._priority_intervals(
            model,
            movement_ids,
            controllers,
            horizon,
        )

        boundaries = {0.0, horizon}
        for rows in service_by_movement.values():
            for start, end in rows:
                boundaries.update((start, end))
        for rows in priority_intervals.values():
            for start, end in rows:
                boundaries.update((start, end))
        bounds = sorted(boundaries)

        movement_queue = {mid: 0.0 for mid in movement_ids}
        movement_arrivals = {mid: 0.0 for mid in movement_ids}
        movement_departures = {mid: 0.0 for mid in movement_ids}
        movement_delay = {mid: 0.0 for mid in movement_ids}
        movement_maximum = {mid: 0.0 for mid in movement_ids}
        movement_overflow = {mid: 0.0 for mid in movement_ids}
        movement_service = {mid: 0.0 for mid in movement_ids}

        lane_arrivals = 0.0
        lane_departures = 0.0
        lane_delay = 0.0
        lane_maximum = 0.0
        lane_overflow = 0.0
        lane_full_seconds = 0.0
        available_service = 0.0
        blocked_seconds = 0.0
        capacity_lost = 0.0
        expected_before_blocking_values = []

        for start, end in zip(bounds, bounds[1:]):
            duration = end - start
            midpoint = (start + end) / 2
            eligible = {
                mid
                for mid in movement_ids
                if self._inside(midpoint, service_by_movement[mid])
            }
            # queue_total = sum(movement_queue.values())
            proportions = movement_proportions(movement_queue, demand_by_movement)

            priority_factors = {
                mid: self._priority_factor(
                    model,
                    mid,
                    priority_intervals,
                    midpoint,
                )
                for mid in movement_ids
            }
            weighted_factor = sum(
                proportions[mid] * priority_factors[mid] for mid in eligible
            )
            base_service_rate = saturation / 3600.0
            potential_rate = base_service_rate * weighted_factor

            blocking = front_blocking_state(
                movement_queue,
                demand_by_movement,
                eligible,
                potential_rate,
                duration,
            )
            if not isinf(blocking.expected_discharge_before_blocking_pcu):
                expected_before_blocking_values.append(
                    blocking.expected_discharge_before_blocking_pcu
                )

            active_duration = blocking.service_duration_before_blocking_s
            blocked_duration = duration - active_duration
            blocked_seconds += blocked_duration
            capacity_lost += potential_rate * blocked_duration

            # First segment: service available until expected front blocking.
            segment_results = []
            if active_duration > 0:
                segment_results.append(
                    self._solve_lane_segment(
                        movement_queue,
                        arrival_rates,
                        eligible,
                        priority_factors,
                        saturation,
                        active_duration,
                        lane.storage_pcu,
                    )
                )
            if blocked_duration > 0:
                segment_results.append(
                    self._solve_lane_segment(
                        movement_queue,
                        arrival_rates,
                        set(),
                        priority_factors,
                        saturation,
                        blocked_duration,
                        lane.storage_pcu,
                    )
                )

            for segment in segment_results:
                lane_arrivals += segment["arrivals"]
                lane_departures += segment["departures"]
                lane_delay += segment["delay"]
                lane_overflow += segment["overflow"]
                lane_full_seconds += segment["full_seconds"]
                lane_maximum = max(lane_maximum, segment["maximum_queue"])
                available_service += segment["available_service"]
                for mid in movement_ids:
                    movement_arrivals[mid] += segment["movement_arrivals"][mid]
                    movement_departures[mid] += segment["movement_departures"][mid]
                    movement_delay[mid] += segment["movement_delay"][mid]
                    movement_overflow[mid] += segment["movement_overflow"][mid]
                    movement_service[mid] += segment["movement_service"][mid]
                    movement_maximum[mid] = max(
                        movement_maximum[mid],
                        segment["movement_maximum"][mid],
                    )

        final_queue = sum(movement_queue.values())
        storage_utilisation = (
            lane_maximum / lane.storage_pcu if lane.storage_pcu > 0 else 0.0
        )
        accessible_capacity = available_service / horizon * 3600.0 if horizon else 0.0
        accessible_dos = self._dos(lane_demand, accessible_capacity)

        lane_timing = None
        lane_nominal_capacity = None
        lane_nominal_dos = None
        if len(signal_groups) == 1:
            lane_timing = green_time(
                controller,
                signal_groups[0],
                model.start_displacement_s,
                model.end_displacement_s,
            )
            lane_nominal_capacity = nominal_capacity_pcu_per_hour(
                saturation,
                lane_timing.effective_green_ratio,
            )
            lane_nominal_dos = nominal_degree_of_saturation(
                lane_demand,
                lane_nominal_capacity,
            )

        lane_result = AnalyticalLaneResult(
            lane_id=lane_id,
            intersection_id=lane.intersection_id,
            movement_ids=tuple(movement_ids),
            signal_group_ids=signal_groups,
            demand_pcu_per_hour=lane_demand,
            saturation_flow_pcu_per_hour=saturation,
            cycle_time_s=controller.cycle_time_s,
            signal_green_s=lane_timing.signal_green_s if lane_timing else None,
            start_displacement_s=model.start_displacement_s,
            end_displacement_s=model.end_displacement_s,
            effective_green_s=lane_timing.effective_green_s if lane_timing else None,
            effective_green_ratio=(
                lane_timing.effective_green_ratio if lane_timing else None
            ),
            nominal_capacity_pcu_per_hour=lane_nominal_capacity,
            nominal_degree_of_saturation=lane_nominal_dos,
            simulated_service_capacity_pcu_per_hour=accessible_capacity,
            simulated_degree_of_saturation=accessible_dos,
            arrivals_pcu=lane_arrivals,
            departures_pcu=lane_departures,
            final_queue_pcu=final_queue,
            maximum_queue_pcu=lane_maximum,
            maximum_queue_m=lane_maximum * model.pcu_length_m,
            total_delay_pcu_hours=lane_delay / 3600.0,
            mean_delay_seconds_per_pcu=(
                lane_delay / lane_departures if lane_departures > 0 else 0.0
            ),
            unserved_demand_pcu=max(0.0, lane_arrivals - lane_departures),
            storage_pcu=lane.storage_pcu,
            storage_utilisation=storage_utilisation,
            storage_overflow_pcu=lane_overflow,
            storage_full_seconds=lane_full_seconds,
            capacity_method=capacity_method(lane.saturation_flow),
            shared_lane_model=(
                "geometric_front_blocking"
                if len(signal_groups) > 1
                else "common_signal_group"
            ),
            blocked_seconds=blocked_seconds,
            capacity_lost_to_blocking_pcu=capacity_lost,
        )

        movement_results = {}
        for movement in movements:
            mid = movement.movement_id
            timing = green_time(
                controller,
                movement.signal_group_id,
                model.start_displacement_s,
                model.end_displacement_s,
            )
            nominal_capacity = nominal_capacity_pcu_per_hour(
                saturation * demand_shares[mid],
                timing.effective_green_ratio,
            )
            accessible_movement_capacity = (
                movement_service[mid] / horizon * 3600.0 if horizon else 0.0
            )
            movement_results[mid] = AnalyticalMovementResult(
                movement_id=mid,
                intersection_id=movement.intersection_id,
                lane_id=lane_id,
                to_lane_id=movement.to_lane_id,
                signal_group_id=movement.signal_group_id,
                movement_type=movement.movement_type,
                demand_pcu_per_hour=demand_by_movement[mid],
                saturation_flow_pcu_per_hour=saturation,
                cycle_time_s=controller.cycle_time_s,
                signal_green_s=timing.signal_green_s,
                start_displacement_s=timing.start_displacement_s,
                end_displacement_s=timing.end_displacement_s,
                effective_green_s=timing.effective_green_s,
                effective_green_ratio=timing.effective_green_ratio,
                nominal_capacity_pcu_per_hour=nominal_capacity,
                nominal_degree_of_saturation=self._dos(
                    demand_by_movement[mid], nominal_capacity
                ),
                simulated_service_capacity_pcu_per_hour=(accessible_movement_capacity),
                simulated_degree_of_saturation=self._dos(
                    demand_by_movement[mid], accessible_movement_capacity
                ),
                arrivals_pcu=movement_arrivals[mid],
                departures_pcu=movement_departures[mid],
                final_queue_pcu=movement_queue[mid],
                maximum_queue_pcu=movement_maximum[mid],
                maximum_queue_m=movement_maximum[mid] * model.pcu_length_m,
                total_delay_pcu_hours=movement_delay[mid] / 3600.0,
                mean_delay_seconds_per_pcu=(
                    movement_delay[mid] / movement_departures[mid]
                    if movement_departures[mid] > 0
                    else 0.0
                ),
                unserved_demand_pcu=max(
                    0.0, movement_arrivals[mid] - movement_departures[mid]
                ),
                storage_overflow_pcu=movement_overflow[mid],
                storage_full_seconds=(
                    lane_full_seconds if demand_shares[mid] > 0 else 0
                ),
                capacity_method=capacity_method(lane.saturation_flow),
                shared_lane_model=lane_result.shared_lane_model,
                blocked_seconds=blocked_seconds,
                expected_discharge_before_blocking_pcu=(
                    sum(expected_before_blocking_values)
                    / len(expected_before_blocking_values)
                    if expected_before_blocking_values
                    else None
                ),
            )

        return lane_result, movement_results

    @staticmethod
    def _solve_lane_segment(
        movement_queue,
        arrival_rates,
        eligible,
        priority_factors,
        saturation,
        duration,
        storage,
    ):
        mids = tuple(movement_queue)
        queue_total = sum(movement_queue.values())
        arrival_total = sum(arrival_rates.values())
        proportions = movement_proportions(movement_queue, arrival_rates)
        weights = {
            mid: (proportions[mid] * priority_factors[mid] if mid in eligible else 0.0)
            for mid in mids
        }
        weight_total = sum(weights.values())
        service_rate = saturation / 3600.0 if weight_total > 0 else 0.0
        result = solve_interval(
            queue_total,
            arrival_total,
            service_rate,
            duration,
            storage,
        )

        departure_shares = (
            {mid: weights[mid] / weight_total for mid in mids}
            if weight_total > 0
            else {mid: 0.0 for mid in mids}
        )
        arrival_shares = movement_proportions(arrival_rates, arrival_rates)
        queue_reduction = queue_total + result.admitted_arrivals - result.final_queue
        for mid in mids:
            admitted_mid = result.admitted_arrivals * arrival_shares[mid]
            departed_mid = result.departures * departure_shares[mid]
            movement_queue[mid] = max(
                0.0,
                movement_queue[mid] + admitted_mid - departed_mid,
            )

        # Reconcile numerical residual to the exact lane final queue.
        residual = result.final_queue - sum(movement_queue.values())
        if abs(residual) > 1e-10 and mids:
            movement_queue[mids[0]] += residual

        queue_shares = movement_proportions(movement_queue, arrival_rates)
        return {
            "arrivals": result.arrivals,
            "departures": result.departures,
            "delay": result.delay_pcu_seconds,
            "overflow": result.overflow,
            "full_seconds": result.storage_full_seconds,
            "maximum_queue": result.maximum_queue,
            "available_service": service_rate * duration,
            "movement_arrivals": {
                mid: result.arrivals * arrival_shares[mid] for mid in mids
            },
            "movement_departures": {
                mid: result.departures * departure_shares[mid] for mid in mids
            },
            "movement_delay": {
                mid: result.delay_pcu_seconds * queue_shares[mid] for mid in mids
            },
            "movement_overflow": {
                mid: result.overflow * arrival_shares[mid] for mid in mids
            },
            "movement_service": {
                mid: service_rate * duration * departure_shares[mid] for mid in mids
            },
            "movement_maximum": {
                mid: result.maximum_queue * queue_shares[mid] for mid in mids
            },
            "queue_reduction": queue_reduction,
        }

    @staticmethod
    def _inside(time_s, intervals):
        return any(start <= time_s < end for start, end in intervals)

    @staticmethod
    def _dos(demand, capacity):
        if capacity > 0:
            return demand / capacity
        return 999.0 if demand > 0 else 0.0

    @staticmethod
    def _priority_intervals(model, movement_ids, controllers, horizon):
        output = {mid: () for mid in movement_ids}
        for conflict in model.conflicts:
            if conflict.yielding_movement_id not in output:
                continue
            rows = []
            for priority_id in conflict.priority_movement_ids:
                priority = model.movements[priority_id]
                controller = controllers[
                    model.intersections[priority.intersection_id].controller_id
                ]
                rows.extend(
                    service_intervals(
                        controller,
                        priority.signal_group_id,
                        horizon,
                        model.start_displacement_s,
                        model.end_displacement_s,
                    )
                )
            output[conflict.yielding_movement_id] = tuple(rows)
        return output

    @staticmethod
    def _priority_factor(model, movement_id, priority_intervals, time_s):
        active = {
            priority_id
            for conflict in model.conflicts
            if conflict.yielding_movement_id == movement_id
            for priority_id in conflict.priority_movement_ids
            if any(
                start <= time_s < end
                for start, end in priority_intervals.get(movement_id, ())
            )
        }
        return active_capacity_factor(model, movement_id, active)
