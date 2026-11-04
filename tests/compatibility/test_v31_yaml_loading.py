from pathlib import Path
import yaml
from traffic_model.loader import load_model

def test_current_v4_loader_accepts_v31_lane_and_movement_schema(tmp_path):
    source = Path(__file__).parents[2] / 'tests' / 'prior_versions' / 'configs' / 'example_optimisation.yaml'
    old = yaml.safe_load(source.read_text(encoding='utf-8'))
    # Adapt only the genuinely renamed plural controller/network envelope fields.
    # Deliberately leave lanes/movements without intersection_id to guard the reported regression.
    old['intersections'] = [{'id':'I1','controller_id':old['controller']['id'],'movement_ids':[m['id'] for m in old['movements']]}]
    old['controllers'] = [{**old.pop('controller'),'intersection_id':'I1'}]
    for phase in old['phases']:
        phase['controller_id'] = old['controllers'][0]['id']
    old['origin_destination_matrix'] = {'values': old['origin_destination_matrix']['values']}
    path = tmp_path / 'v31_style.yaml'
    path.write_text(yaml.safe_dump(old, sort_keys=False), encoding='utf-8')
    model = load_model(path)
    assert all(l.intersection_id == 'I1' for l in model.lanes.values())
    assert all(m.intersection_id == 'I1' for m in model.movements.values())
