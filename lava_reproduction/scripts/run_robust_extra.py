#!/usr/bin/env python3
"""Robustness additions made after review (descriptive), reusing run_improvement.run_suite
without changing registered code. control: unmodified protocol on the robustness seeds.
load: arrival rate x2 with 5,000 VMs (same ~312 h arrival window, ~41% steady-state offered load)."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import run_improvement as ri
SUITES={'control':('robust_control',{'protocol':{}}),'load':('robust_load',{'arrival_x2':{'arrival_rate':16,'vms':5000}})}

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',choices=list(SUITES),required=True);p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    c=json.loads((root/'configs/report_scale.json').read_text());name,variants=SUITES[a.suite]
    spec=dict(seeds=range(2000,2050),settings=ri.PRIMARY_SETTINGS,policies=ri.CORE,taus=[c['threshold']],variants=variants)
    ri.run_suite(name,spec,c,a.workers,None,root/'results/improvement'/name)
if __name__=='__main__':main()
