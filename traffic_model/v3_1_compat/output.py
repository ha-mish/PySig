from pathlib import Path
from dataclasses import asdict
import csv,json
def _csv(path,rows):
 rows=list(rows)
 if rows:
  with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def write(result,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
 for x in result.candidates:
  d=asdict(x);d['phase_durations_s']='|'.join(map(str,x.phase_durations_s));rows.append(d)
 _csv(out/'optimisation_candidates.csv',rows)
 b=asdict(result.best);b.update({'phase_durations_s':list(result.best.phase_durations_s),'outer_iterations':result.outer_iterations,'signal_plan_stable':result.signal_plan_stable,'route_flows_stable':result.route_flows_stable,'optimisation_converged':result.converged});(out/'optimisation_summary.json').write_text(json.dumps(b,indent=2),encoding='utf-8')
