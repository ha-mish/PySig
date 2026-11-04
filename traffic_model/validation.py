def validate(model):
 issues=[]
 for lid,l in model.lanes.items():
  if l.parent_lane_id and l.parent_lane_id not in model.lanes:issues.append(f'Lane {lid}: parent_lane_id {l.parent_lane_id} does not exist')
 for mid,m in model.movements.items():
  if m.from_lane_id not in model.lanes:issues.append(f'Movement {mid}: from_lane_id {m.from_lane_id} does not exist')
  if m.to_lane_id is not None and m.to_lane_id not in model.lanes:issues.append(f'Movement {mid}: to_lane_id {m.to_lane_id} does not exist')
  if m.intersection_id not in model.intersections:issues.append(f'Movement {mid}: intersection {m.intersection_id} does not exist')
 for iid,i in model.intersections.items():
  if i.controller_id not in model.controllers:issues.append(f'Intersection {iid}: controller {i.controller_id} does not exist')
 for cid,c in model.controllers.items():
  total=sum(p.duration_s+p.intergreen_after_s for p in c.phases)
  if abs(total-c.cycle_time_s)>1e-6:issues.append(f'Controller {cid}: phases plus intergreens total {total:g}s but cycle_time_s is {c.cycle_time_s:g}s')
 for od,q in model.od.items():
  if q>0 and not any((r.origin_zone_id,r.destination_zone_id)==od for r in model.routes.values()):issues.append(f'OD {od}: demand {q:g} has no route')
 for rid,r in model.routes.items():
  for mid in r.movement_ids:
   if mid not in model.movements:issues.append(f'Route {rid}: movement {mid} does not exist')
 return issues
