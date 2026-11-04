from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True,slots=True)
class Lane: lane_id:str; storage_pcu:float; saturation_flow:dict[str,Any]; parent_lane_id:str|None=None
@dataclass(frozen=True,slots=True)
class Movement: movement_id:str; from_lane_id:str; signal_group_id:str; free_flow_time_s:float=0
@dataclass(frozen=True,slots=True)
class Conflict: yielding_movement_id:str; priority_movement_ids:tuple[str,...]; active_capacity_factor:float=1
@dataclass(frozen=True,slots=True)
class Phase: phase_id:str; active_signal_groups:tuple[str,...]; duration_s:float; intergreen_after_s:float=0
@dataclass(frozen=True,slots=True)
class Controller: controller_id:str; cycle_time_s:float; offset_s:float; phases:tuple[Phase,...]
@dataclass(frozen=True,slots=True)
class Route: route_id:str; origin_zone_id:str; destination_zone_id:str; movement_ids:tuple[str,...]
@dataclass(frozen=True,slots=True)
class AssignmentSettings:
 max_iterations:int=30; relative_gap_tolerance:float=.01; max_flow_change_tolerance:float=1; conservation_tolerance:float=1e-6
@dataclass(frozen=True,slots=True)
class OptimisationSettings:
 objective:str='delay'; cycle_times_s:tuple[float,...]=(90,); split_step_s:float=5; offset_step_s:float=5; minimum_phase_green_s:float=10; maximum_candidates:int=1000; queue_storage_utilisation_limit:float=1; outer_iterations:int=3; outer_flow_tolerance:float=1; prc_target_dos:float=.9; unconverged_candidate_policy:str='reject'
@dataclass(frozen=True,slots=True)
class Model:
 model_id:str; lanes:dict; movements:dict; conflicts:tuple; controller:Controller; routes:dict; od:dict; assignment:AssignmentSettings; optimisation:OptimisationSettings; pcu_length_m:float=7.35; start_displacement_s:float=3; end_displacement_s:float=3; reporting_cycles:int=10; warm_up_cycles:int=3
