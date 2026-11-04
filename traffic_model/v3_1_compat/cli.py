import argparse,subprocess,sys
from pathlib import Path
from .loader import load_model
from .optimisation import optimise
from .output import write
def main(argv,default):
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd');o=sub.add_parser('optimise');o.add_argument('--config',type=Path,default=default);o.add_argument('--output',type=Path,default=Path('results'));o.add_argument('--quiet',action='store_true');sub.add_parser('test');args=p.parse_args(argv);cmd=args.cmd or 'optimise'
 if cmd=='test':return subprocess.call([sys.executable,'-m','pytest'],cwd=Path(__file__).resolve().parents[1])
 config=getattr(args,'config',default);output=getattr(args,'output',Path('results'));quiet=getattr(args,'quiet',False);model=load_model(config)
 def log(r):print(f"Outer {r.outer_iteration} candidate {r.candidate}: cycle={r.cycle_time_s:.0f}s split={r.phase_durations_s} assignment={'CONVERGED' if r.assignment_converged else 'NOT CONVERGED'} ({r.assignment_iterations}/{model.assignment.max_iterations}) OD={'PASS' if r.od_conservation_pass else 'FAIL'} queue={'PASS' if r.queue_constraint_pass else 'FAIL'} feasible={r.feasible}")
 result=optimise(model,None if quiet else log);write(result,output);b=result.best;print(f"Best: cycle={b.cycle_time_s:.0f}s split={b.phase_durations_s}, assignment_converged={b.assignment_converged}, OD_conservation={b.od_conservation_pass}, signal_stable={result.signal_plan_stable}, route_flows_stable={result.route_flows_stable}, overall_converged={result.converged}");print(f'Results: {output.resolve()}');return 0
