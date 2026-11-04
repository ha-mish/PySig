from pathlib import Path
from traffic_model.v3_1_compat.loader import load_model
M=load_model(Path(__file__).parents[2]/'configs'/'example_optimisation.yaml')
def test_multiple_lane_parent():assert M.lanes['L_AB_2'].parent_lane_id=='L_AB_1'
