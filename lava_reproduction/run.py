#!/usr/bin/env python3
"""Run fresh experiments. Numeric report references never enter the simulator."""
import argparse,json,csv,hashlib,platform,subprocess,statistics
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from lava.model import trace
from lava.simulator import simulate,POLICIES
from lava.stats import paired
from lava.charts import plot

def job(args):
    c,seed,setting,policy,tau=args
    return simulate(trace(c,seed),c,seed,setting,policy,tau)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--suite',choices=['smoke','heldout','sweep','validation','all'],default='smoke')
    p.add_argument('--config',default='configs/report_scale.json');p.add_argument('--output',default='results/smoke')
    p.add_argument('--workers',type=int,default=1);p.add_argument('--vms',type=int)
    a=p.parse_args();c=json.loads(Path(a.config).read_text())
    if a.vms:c['vms']=a.vms
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    tasks=[]
    def add(seeds,settings,policies,taus):
        for seed in seeds:
            for setting in settings:
                for policy in policies:
                    for tau in taus:tasks.append((c,seed,setting,policy,tau))
    if a.suite=='smoke':add(range(2),['synthetic','0.85','oracle'],POLICIES,[.3])
    if a.suite in ['heldout','all']:add(range(20,40),['0.25','0.5','0.75','0.85','1.0','synthetic','oracle'],POLICIES,[.3])
    if a.suite in ['sweep','all']:add(range(20),['0.25','0.5','0.75','0.8','0.85','0.9','0.95','1.0','synthetic','oracle'],['best_fit','lava','vm_ca'],[.3])
    if a.suite in ['validation','all']:add(range(200,206),['synthetic'],['best_fit','lava','vm_ca','host_ca'],[.1,.2,.3,.5,.7,.8,.9])
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i,r in enumerate(pool.map(job,tasks)):
            rows.append(r)
            if (i+1)%20==0:print(f'{i+1}/{len(tasks)} runs complete',flush=True)
    with (out/'raw.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summaries=[]
    for tau in sorted({r['threshold'] for r in rows}):
        subset=[r for r in rows if r['threshold']==tau]
        # "all" combines disjoint splits: report each separately, never pool them.
        for split,seeds in [('smoke',range(2)),('initial',range(20)),('heldout',range(20,40)),('validation',range(200,206))]:
            sr=[r for r in subset if r['seed'] in seeds]
            if not sr or (split=='smoke' and a.suite!='smoke') or (split=='initial' and a.suite=='smoke'):continue
            for setting in sorted({r['setting'] for r in sr}):
                for policy in POLICIES:
                    for baseline in (['best_fit','lava','vm_ca'] if policy=='host_ca' else ['best_fit']):
                        if policy==baseline or not any(r['policy']==policy for r in sr):continue
                        if not any(r['policy']==baseline for r in sr):continue
                        mean,lo,hi=paired(sr,policy,baseline,setting)
                        summaries.append(dict(split=split,setting=setting,policy=policy,baseline=baseline,threshold=tau,n=len({r['seed'] for r in sr if r['setting']==setting}),mean=mean,low=lo,high=hi))
    (out/'summary.json').write_text(json.dumps(summaries,indent=2))
    if a.suite=='validation':
        scores={}
        for tau in sorted({r['threshold'] for r in rows}):
            scores[tau]=statistics.mean(s['mean'] for s in summaries if s['threshold']==tau and s['policy']=='host_ca' and s['baseline'] in ['lava','vm_ca'])
        (out/'threshold_selection.json').write_text(json.dumps({'objective':'mean improvement over LAVA and VM CA on synthetic validation only (inferred)','scores':scores,'selected':max(scores,key=scores.get),'report_frozen_threshold':.3},indent=2))
    plot(summaries,out/'comparison.svg','RECONSTRUCTION: paired mean and Student-t 95% CI')
    (out/'manifest.json').write_text(json.dumps({'suite':a.suite,'config':c,'python':platform.python_version(),'runs':len(rows),'config_sha256':hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),'source_sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(Path('lava').glob('*.py'))},'warning':'Fresh synthetic results, NOT recovered original random outcomes.'},indent=2))
    print(f'Wrote {len(rows)} runs to {out}; failures={sum(r["failures"] for r in rows)}')
if __name__=='__main__':main()
