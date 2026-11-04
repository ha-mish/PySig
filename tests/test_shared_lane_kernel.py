from dataclasses import replace
from pathlib import Path
import pytest
from traffic_model.loader import load_model
from traffic_model.simulation import simulate
from traffic_model.assignment import assign
from traffic_model.output import write_outputs

ROOT = Path(__file__).resolve().parents[1]


def shared_lane_model(different_signal_groups=False):
    model = load_model(ROOT / 'configs' / 'example_intersection_optimisation.yaml')
    movements = dict(model.movements)
    right = movements['M_W_RIGHT']
    movements['M_W_RIGHT'] = replace(
        right,
        from_lane_id='W_1',
        signal_group_id='SG_NS' if different_signal_groups else 'SG_EW',
    )
    return replace(model, movements=movements)


def test_same_lane_movement_demands_sum_to_lane_demand():
    model = shared_lane_model()
    result = simulate(model, {'M_W_THROUGH': 500.0, 'M_W_RIGHT': 100.0, 'M_N_THROUGH': 0.0})
    lane = result.lanes['W_1']
    assert lane.demand_pcu_per_hour == pytest.approx(600.0)
    assert lane.arrivals_pcu == pytest.approx(
        result.movements['M_W_THROUGH'].arrivals_pcu
        + result.movements['M_W_RIGHT'].arrivals_pcu
    )


def test_shared_lane_queue_and_delay_are_conserved():
    model = shared_lane_model()
    result = simulate(model, {'M_W_THROUGH': 500.0, 'M_W_RIGHT': 100.0, 'M_N_THROUGH': 0.0})
    lane = result.lanes['W_1']
    movements = [result.movements['M_W_THROUGH'], result.movements['M_W_RIGHT']]
    assert lane.final_queue_pcu == pytest.approx(sum(x.final_queue_pcu for x in movements))
    assert lane.total_delay_pcu_hours == pytest.approx(sum(x.total_delay_pcu_hours for x in movements))
    assert lane.departures_pcu == pytest.approx(sum(x.departures_pcu for x in movements))


def test_lane_capacity_is_not_duplicated_across_movements():
    model = shared_lane_model()
    result = simulate(model, {'M_W_THROUGH': 1000.0, 'M_W_RIGHT': 1000.0, 'M_N_THROUGH': 0.0})
    lane = result.lanes['W_1']
    movement_capacity = (
        result.movements['M_W_THROUGH'].capacity_pcu_per_hour
        + result.movements['M_W_RIGHT'].capacity_pcu_per_hour
    )
    assert movement_capacity == pytest.approx(lane.capacity_pcu_per_hour)
    # The service capacity is measured over the finite reporting horizon.
    # It may differ slightly from the long-run g/C value when the horizon ends
    # part-way through a cycle, but it must never duplicate the lane saturation
    # flow for each movement.
    assert lane.capacity_pcu_per_hour <= lane.saturation_flow_pcu_per_hour + 1e-6


def test_different_signal_groups_use_one_lane_storage():
    model = shared_lane_model(different_signal_groups=True)
    result = simulate(model, {'M_W_THROUGH': 450.0, 'M_W_RIGHT': 150.0, 'M_N_THROUGH': 0.0})
    lane = result.lanes['W_1']
    assert lane.maximum_queue_pcu <= model.lanes['W_1'].storage_pcu + 1e-9
    assert lane.maximum_queue_pcu >= max(
        result.movements['M_W_THROUGH'].maximum_queue_pcu,
        result.movements['M_W_RIGHT'].maximum_queue_pcu,
    )


def test_results_json_and_lane_csv_include_lane_results(tmp_path):
    model = shared_lane_model()
    assignment = assign(model)
    data = write_outputs(model, assignment, tmp_path)
    assert data['schema_version'] == '4.2.2'
    assert data['simulation']['queue_kernel'] == 'shared_lane_fifo_composition'
    assert data['lanes']
    assert (tmp_path / 'lane_results.csv').exists()
