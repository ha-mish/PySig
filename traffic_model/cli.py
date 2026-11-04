import argparse,subprocess,sys
from pathlib import Path
from .loader import load_model
from .validation import validate
from .assignment import assign
from .optimisation import optimise
from .output import write_outputs
def main(argv,default):
 p=argparse.ArgumentParser(description='PySig 4.2.1');sub=p.add_subparsers(dest='cmd')
 for name in ('run','optimise','validate'):
  q=sub.add_parser(name);q.add_argument('--config',type=Path,default=default)
  if name!='validate':q.add_argument('--output',type=Path,default=Path('results'))
  if name=='optimise':q.add_argument('--quiet',action='store_true')
 sub.add_parser('test');a=p.parse_args(argv)
 if a.cmd=='test':return subprocess.call([sys.executable,'-m','pytest'],cwd=Path(__file__).resolve().parents[1])
 config=getattr(a,'config',default);model=load_model(config);issues=validate(model)
 if issues:
  print('Model validation failed:');[print('  ERROR:',x) for x in issues];return 2
 if a.cmd=='validate':print(f'Valid: {model.model_name}');return 0
 cmd=a.cmd or ('optimise' if model.optimisation.mode in ('optimise_network','optimise_intersection') else 'run');out=getattr(a,'output',Path('results'))
 if cmd=='run':
  result=assign(model);write_outputs(model,result,out,model.controllers,None,'final_assignment');print(f'Run complete: converged={result.converged}, movements={len(result.simulation.movements)}')
 else:
  def log(x):print(f'Outer {x.outer_iteration} {x.controller_id} candidate {x.candidate}: cycle={x.cycle_time_s:.0f}s split={x.phase_durations_s} offset={x.offset_s:.0f}s delay={x.network_delay_pcu_hours:.3f} feasible={x.feasible}')
  opt=optimise(model,None if getattr(a,'quiet',False) else log);final=assign(model,opt.controllers,opt.best_assignment.route_flows);write_outputs(model,final,out,opt.controllers,opt,'final_optimised_assignment');print(f'Optimisation complete: converged={opt.converged}, movement results={len(final.simulation.movements)}')
 print(f'Results: {out.resolve()}');return 0
