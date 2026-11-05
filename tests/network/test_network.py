from pathlib import Path

import pytest

from traffic_model.assignment import assign
from traffic_model.loader import load_model
from traffic_model.simulation import effective_green

ROOT = Path(__file__).resolve().parents[2]

CONFIG = (
    ROOT
    / "configs"
    / "example_network_optimisation.yaml"
)

M = load_model(CONFIG)


def test_two_intersections():
    assert len(M.intersections) == 2


def test_fixed_od_conserved():
    result = assign(M)

    assert sum(
        result.route_flows.values()
    ) == pytest.approx(
        700.0,
        abs=1e-6,
    )

    assert (
        result.iterations[-1].conservation_error
        <= M.assignment.conservation_tolerance
    )


def test_link_travel_time_and_storage():
    result = assign(M)

    link = result.simulation.links[
        "LINK_MAIN"
    ]

    assert link.travel_time_s == pytest.approx(
        30.0
    )

    assert (
        result
        .simulation
        .maximum_link_storage_utilisation
        <= 1.0
    )


def test_offset_changes_effective_signal_state():
    controller = M.controllers["C2"]

    state_at_zero = effective_green(
        controller=controller,
        signal_group_id="SG2_MAIN",
        time_s=0.0,
        start_displacement_s=(
            M.start_displacement_s
        ),
        end_displacement_s=(
            M.end_displacement_s
        ),
    )

    state_at_25 = effective_green(
        controller=controller,
        signal_group_id="SG2_MAIN",
        time_s=25.0,
        start_displacement_s=(
            M.start_displacement_s
        ),
        end_displacement_s=(
            M.end_displacement_s
        ),
    )

    assert state_at_zero != state_at_25


def test_routes_cross_intersections():
    route = M.routes["R_MAIN"]

    intersection_ids = [
        M.movements[
            movement_id
        ].intersection_id
        for movement_id
        in route.movement_ids
    ]

    assert intersection_ids == [
        "I1",
        "I2",
    ]


def test_network_movements_report_signal_timing():
    result = assign(M)

    movement = result.simulation.movements[
        "M1_MAIN"
    ]

    assert movement.cycle_time_s > 0

    assert movement.signal_green_s >= 0

    assert (
        movement.start_displacement_s
        == pytest.approx(
            M.start_displacement_s
        )
    )

    assert (
        movement.end_displacement_s
        == pytest.approx(
            M.end_displacement_s
        )
    )

    assert (
        movement.effective_green_s
        >= 0
    )

    assert (
        0.0
        <= movement.effective_green_ratio
        <= 1.0
    )


def test_network_nominal_capacity_is_auditable():
    result = assign(M)

    movement = result.simulation.movements[
        "M1_MAIN"
    ]

    expected_capacity = (
        movement.saturation_flow_pcu_per_hour
        * movement.effective_green_ratio
    )

    assert (
        movement.nominal_capacity_pcu_per_hour
        == pytest.approx(
            expected_capacity
        )
    )


def test_network_nominal_dos_is_auditable():
    result = assign(M)

    movement = result.simulation.movements[
        "M1_MAIN"
    ]

    capacity = (
        movement.nominal_capacity_pcu_per_hour
    )

    if capacity > 0:
        expected_dos = (
            movement.demand_pcu_per_hour
            / capacity
        )
    elif movement.demand_pcu_per_hour > 0:
        expected_dos = 999.0
    else:
        expected_dos = 0.0

    assert (
        movement.nominal_degree_of_saturation
        == pytest.approx(
            expected_dos
        )
    )


def test_network_simulated_dos_is_auditable():
    result = assign(M)

    movement = result.simulation.movements[
        "M1_MAIN"
    ]

    capacity = (
        movement
        .simulated_service_capacity_pcu_per_hour
    )

    if capacity > 0:
        expected_dos = (
            movement.demand_pcu_per_hour
            / capacity
        )
    elif movement.demand_pcu_per_hour > 0:
        expected_dos = 999.0
    else:
        expected_dos = 0.0

    assert (
        movement.simulated_degree_of_saturation
        == pytest.approx(
            expected_dos
        )
    )


def test_network_lane_queues_respect_storage():
    result = assign(M)

    for lane_id, lane_result in (
        result.simulation.lanes.items()
    ):
        model_lane = M.lanes[lane_id]

        assert (
            lane_result.maximum_queue_pcu
            <= model_lane.storage_pcu
            + 1e-9
        )


def test_network_lane_queue_equals_movement_subqueues():
    result = assign(M)

    for lane in result.simulation.lanes.values():
        movement_queue = sum(
            result
            .simulation
            .movements[movement_id]
            .final_queue_pcu
            for movement_id
            in lane.movement_ids
        )

        assert (
            lane.final_queue_pcu
            == pytest.approx(
                movement_queue
            )
        )


def test_network_lane_delay_equals_movement_delay():
    result = assign(M)

    for lane in result.simulation.lanes.values():
        movement_delay = sum(
            result
            .simulation
            .movements[movement_id]
            .total_delay_pcu_hours
            for movement_id
            in lane.movement_ids
        )

        assert (
            lane.total_delay_pcu_hours
            == pytest.approx(
                movement_delay
            )
        )