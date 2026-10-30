#!/usr/bin/env python3
import sys,json,csv,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lava.model import trace
p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=20);p.add_argument('--output',default='trace_seed20.csv');p.add_argument('--config',default='configs/report_scale.json');a=p.parse_args()
c=json.loads(Path(a.config).read_text())
with open(a.output,'w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','arrival_hours','duration_hours','cpu','memory','profile'])
 for record in trace(c,a.seed):
  r=record.request;w.writerow([r.id,r.arrival,record.duration,r.cpu,r.mem,r.profile])
print(a.output)
