from .domain import Route

def enumerate_routes(model):
 supplied=dict(model.routes)
 # Directed adjacency joins a movement to movements whose from-lane equals its to-lane.
 adjacency={mid:[] for mid in model.movements}
 for a in model.movements.values():
  if a.to_lane_id is not None:
   adjacency[a.movement_id]=[b.movement_id for b in model.movements.values() if b.from_lane_id==a.to_lane_id]
 counter=1
 for oz in model.zones.values():
  for dz in model.zones.values():
   if oz.zone_id==dz.zone_id: continue
   existing=[r for r in supplied.values() if r.origin_zone_id==oz.zone_id and r.destination_zone_id==dz.zone_id]
   if existing: continue
   found=[]
   def dfs(mid,path):
    if len(path)>model.assignment.max_movements_per_route or len(found)>=model.assignment.max_routes_per_od:return
    if mid in path:return
    nxt=path+(mid,)
    if mid in dz.destination_movement_ids: found.append(nxt); return
    for child in adjacency.get(mid,[]): dfs(child,nxt)
   for start in oz.origin_movement_ids:
    if start in model.movements: dfs(start,())
   for path in found:
    rid=f'R_AUTO_{counter:04d}'; counter+=1
    supplied[rid]=Route(rid,oz.zone_id,dz.zone_id,path)
 return supplied
