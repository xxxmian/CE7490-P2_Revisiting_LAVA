#!/usr/bin/env python3
"""Post-hoc (not pre-registered): how often does each confidence gate pass requests whose
controlled prediction came from the correct vs the incorrect error bucket? Uses the harness's
own random stream to recover the hidden bucket; the schedulers never see it."""
import argparse,json,random,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from lava.model import Predictor,BayesPredictor,trace
C=json.loads((root/'configs/report_scale.json').read_text())

def buckets(seed,acc,records):
    # Mirrors Predictor.__init__: one uniform draw for the bucket, then one Gaussian draw.
    rng=random.Random(seed+10_000_019);good,bad=C.get('noise_sigmas',[.001,3.]);out=[]
    for _ in records:
        correct=rng.random()<acc;rng.gauss(0,good if correct else bad);out.append(correct)
    return out

def job(args):
    seed,setting=args;records=trace(C,seed);acc=float(setting);tau=C['threshold']
    raw,fused=Predictor(C,seed,setting,records),BayesPredictor(C,seed,setting,records);counts={}
    for rec,correct in zip(records,buckets(seed,acc,records)):
        req=rec.request
        for name,pred in (('original',raw),('fused',fused)):
            key=(name,'correct' if correct else 'incorrect');n,k=counts.get(key,(0,0))
            counts[key]=(n+1,k+(pred.predict(req,req.arrival)[1]>=tau))
    return setting,counts

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=1);p.add_argument('--output',default='results/improvement/gate_by_bucket.json');a=p.parse_args()
    settings=['0.25','0.5','0.75','0.85'];tasks=[(s,st) for s in range(1000,1100) for st in settings];total={}
    with ProcessPoolExecutor(a.workers) as pool:
        for setting,counts in pool.map(job,tasks,chunksize=2):
            for key,(n,k) in counts.items():
                N,K=total.get((setting,)+key,(0,0));total[(setting,)+key]=(N+n,K+k)
    out={'note':'post hoc, seeds 1000-1099, tau = report threshold; share of arrivals routed to LAVA by error bucket','threshold':C['threshold'],'rows':[]}
    for setting in settings:
        for name in ('original','fused'):
            row={'setting':setting,'confidence':name}
            for b in ('correct','incorrect'):
                n,k=total[(setting,name,b)];row[f'{b}_n']=n;row[f'{b}_pass']=k/n
            out['rows'].append(row)
    Path(a.output).write_text(json.dumps(out,indent=2))
    for r in out['rows']:print(f"{r['setting']:5s} {r['confidence']:8s} pass|correct={r['correct_pass']:.3f}  pass|incorrect={r['incorrect_pass']:.3f}  (n={r['correct_n']}/{r['incorrect_n']})")
if __name__=='__main__':main()
