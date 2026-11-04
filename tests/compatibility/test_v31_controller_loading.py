from pathlib import Path
import yaml
from traffic_model.loader import load_model

def test_v4_loader_accepts_singular_v31_controller(tmp_path):
    source = Path(__file__).parents[2] / 'tests' / 'prior_versions' / 'configs' / 'example_optimisation.yaml'
    data = yaml.safe_load(source.read_text(encoding='utf-8'))
    # Keep the V3.1 singular controller and phases without controller_id.
    data['intersections'] = [{'id':'I1','controller_id':data['controller']['id'],'movement_ids':[m['id'] for m in data['movements']]}]
    path = tmp_path / 'legacy_controller.yaml'
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    model = load_model(path)
    assert set(model.controllers) == {'C1'}
    assert model.controllers['C1'].intersection_id == 'I1'
    assert len(model.controllers['C1'].phases) == len(data['phases'])
