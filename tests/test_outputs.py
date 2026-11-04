import json,subprocess,sys
from pathlib import Path
import pytest
from traffic_model.loader import load_model
from traffic_model.assignment import assign
from traffic_model.output import write_outputs
ROOT=Path(__file__).resolve().parents[1]
REQUIRED={'movement_id','lane_id','demand_pcu_per_hour','saturation_flow_pcu_per_hour','arrivals_pcu','departures_pcu','final_queue_pcu','maximum_queue_pcu','maximum_queue_m','total_delay_pcu_hours','mean_delay_seconds_per_pcu','degree_of_saturation','unserved_demand_pcu','storage_full_seconds','capacity_method'}
def test_rich_results_json(tmp_path):
 m=load_model(ROOT/'configs'/'example_intersection_optimisation.yaml');a=assign(m);write_outputs(m,a,tmp_path);d=json.loads((tmp_path/'results.json').read_text());assert d['schema_version']=='4.2.2';assert REQUIRED<=set(d['movements'][0]);assert (tmp_path/'movement_results.csv').exists();assert d['summary']['od_conservation_error']<=1e-6
def test_to_lane_id_loaded_and_reported(tmp_path):
 m=load_model(ROOT/'configs'/'example_intersection_optimisation.yaml');assert m.movements['M_W_THROUGH'].to_lane_id=='E_OUT';a=assign(m);d=write_outputs(m,a,tmp_path);x=next(x for x in d['movements'] if x['movement_id']=='M_W_THROUGH');assert x['to_lane_id']=='E_OUT'
def test_queue_metres_consistent():
 m=load_model(ROOT/'configs'/'example_intersection_optimisation.yaml');a=assign(m);x=a.simulation.movements['M_W_THROUGH'];assert x.maximum_queue_m==pytest.approx(x.maximum_queue_pcu*m.pcu_length_m)
