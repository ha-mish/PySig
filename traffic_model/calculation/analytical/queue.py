"""Exact deterministic fluid-queue interval calculations."""

from dataclasses import dataclass
from math import inf


@dataclass(frozen=True, slots=True)
class QueueIntervalResult:
    final_queue: float
    maximum_queue: float
    arrivals: float
    admitted_arrivals: float
    departures: float
    overflow: float
    storage_full_seconds: float
    delay_pcu_seconds: float


def solve_interval(
    queue: float,
    arrival_rate: float,
    service_rate: float,
    duration: float,
    storage: float = inf,
):
    """Solve one constant-rate finite-storage queue interval exactly."""

    if duration <= 0:
        return QueueIntervalResult(queue, queue, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    arrivals = arrival_rate * duration
    storage = max(0.0, storage)

    if queue <= 1e-12 and service_rate >= arrival_rate:
        return QueueIntervalResult(
            0.0, 0.0, arrivals, arrivals, arrivals, 0.0, 0.0, 0.0
        )

    net_rate = arrival_rate - service_rate

    if net_rate >= 0:
        unconstrained_final = queue + net_rate * duration
        maximum_queue = min(storage, max(queue, unconstrained_final))

        if net_rate > 0 and queue < storage and unconstrained_final > storage:
            time_to_full = min(duration, max(0.0, (storage - queue) / net_rate))
            full_time = duration - time_to_full
            delay = (queue + storage) * time_to_full / 2 + storage * full_time
            departures = service_rate * duration
            admitted = min(arrivals, max(0.0, departures + storage - queue))
            overflow = arrivals - admitted
            final_queue = storage
        elif queue >= storage - 1e-12:
            full_time = duration
            departures = service_rate * duration
            admitted = min(arrivals, departures)
            overflow = arrivals - admitted
            final_queue = storage
            delay = storage * duration
        else:
            full_time = 0.0
            final_queue = unconstrained_final
            departures = arrivals + queue - final_queue
            admitted = arrivals
            overflow = 0.0
            delay = (queue + final_queue) * duration / 2

        return QueueIntervalResult(
            final_queue,
            maximum_queue,
            arrivals,
            admitted,
            max(0.0, departures),
            max(0.0, overflow),
            full_time,
            delay,
        )

    time_to_clear = queue / (-net_rate) if queue > 0 else 0.0
    if time_to_clear >= duration:
        final_queue = max(0.0, queue + net_rate * duration)
        delay = (queue + final_queue) * duration / 2
        departures = arrivals + queue - final_queue
    else:
        final_queue = 0.0
        delay = queue * time_to_clear / 2
        departures = arrivals + queue

    return QueueIntervalResult(
        final_queue,
        queue,
        arrivals,
        arrivals,
        max(0.0, departures),
        0.0,
        0.0,
        delay,
    )
