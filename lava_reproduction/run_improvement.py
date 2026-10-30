#!/usr/bin/env python3
"""Improvement study: prior-fused lifetime prediction (*_bayes) on fresh seeds.
Hypotheses are pre-registered in configs/improvement_protocol.json. Report values never enter."""
import argparse,json,csv,hashlib,platform,os,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from lava.model import trace
from lava.simulator import simulate,POLICIES,BAYES_POLICIES
from lava.stats import paired_diffs,t_test,holm

CONTROLLED=['0.25','0.5','0.75','0.85','1.0']
CORE=['best_fit','nilas','lava','vm_ca','nilas_bayes','lava_bayes','vm_ca_bayes']
PRIMARY_SETTINGS=['0.25','0.5','0.75','0.85']; PRIMARY_BASELINES=['lava','best_fit']
METRICS=['empty_pct','empty_pct_arrivals']

def scaled(c,f):return {k:[p,a*f,b*f] for k,(p,a,b) in c['profiles'].items()}

def suites(c):
    full=dict(settings=CONTROLLED+['synthetic','oracle'],policies=POLICIES+BAYES_POLICIES,taus=[c['threshold']],variants={'protocol':{}})
    return {'test':dict(full,seeds=range(1000,1100)),
            'legacy':dict(full,seeds=range(20,40)),
            'tau':dict(seeds=range(200,220),settings=PRIMARY_SETTINGS,policies=['best_fit','lava','vm_ca','vm_ca_bayes'],taus=[.1,.2,.3,.5,.7,.8,.9],variants={'protocol':{}}),
            'robust':dict(seeds=range(2000,2050),settings=PRIMARY_SETTINGS,policies=CORE,taus=[c['threshold']],variants={
                'bad_sigma=1':{'noise_sigmas':[.001,1.]},
                'bad_sigma=0.5':{'noise_sigmas':[.001,.5]},
                'fusion_assumes_3_true_1':{'noise_sigmas':[.001,1.],'fusion_sigmas':[.001,3.]},
                'fusion_assumes_1_true_3':{'fusion_sigmas':[.001,1.]},
                'prior_means_x0.5':{'prior_profiles':scaled(c,.5)},
                'prior_means_x2':{'prior_profiles':scaled(c,2.)},
                'hosts=90':{'hosts':90}})}

def comparisons(policies):
    pairs=[(p,'best_fit') for p in policies if p!='best_fit']+[(b,b[:-len('_bayes')]) for b in BAYES_POLICIES]
    pairs+=[('vm_ca_bayes','lava'),('vm_ca_bayes','nilas'),('host_ca','vm_ca'),('host_ca_bayes','vm_ca_bayes')]
    return [(p,b) for p,b in dict.fromkeys(pairs) if p in policies and b in policies]

def job(args):
    c,variant,seed,setting,policy,tau=args
    r=simulate(trace(c,seed),c,seed,setting,policy,tau);r['variant']=variant
    return r

def run_suite(name,spec,base,workers,max_seeds,out):
    seeds=list(spec['seeds'])[:max_seeds] if max_seeds else list(spec['seeds'])
    tasks=[(dict(base,**cfg),variant,seed,setting,policy,tau) for variant,cfg in spec['variants'].items()
           for seed in seeds for setting in spec['settings'] for policy in spec['policies'] for tau in spec['taus']]
    out.mkdir(parents=True,exist_ok=True);rows=[];start=time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,r in enumerate(pool.map(job,tasks,chunksize=4)):
            rows.append(r)
            if (i+1)%500==0:print(f'[{name}] {i+1}/{len(tasks)} runs, {time.time()-start:.0f}s',flush=True)
    assert all(r['failures']==0 for r in rows),'scheduling failures invalidate paired comparisons'
    with (out/'raw.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summaries=[]
    for variant in spec['variants']:
        for tau in spec['taus']:
            sr=[r for r in rows if r['variant']==variant and r['threshold']==tau]
            for setting in spec['settings']:
                for policy,baseline in comparisons(spec['policies']):
                    for metric in METRICS:
                        mean,lo,hi,p=t_test(paired_diffs(sr,policy,baseline,setting,metric))
                        summaries.append(dict(suite=name,variant=variant,threshold=tau,setting=setting,policy=policy,baseline=baseline,metric=metric,
                            n=len(seeds),mean=mean,low=lo,high=hi,p=p,primary=name=='test' and metric=='empty_pct' and policy=='vm_ca_bayes' and baseline in PRIMARY_BASELINES and setting in PRIMARY_SETTINGS))
    family=[s for s in summaries if s['primary']]
    for s,adj in zip(family,holm([s['p'] for s in family])):s['p_holm']=adj
    (out/'summary.json').write_text(json.dumps(summaries,indent=2))
    sources=sorted(Path('lava').glob('*.py'))+[Path('run_improvement.py'),Path('configs/improvement_protocol.json')]
    (out/'manifest.json').write_text(json.dumps({'suite':name,'seeds':[seeds[0],seeds[-1]],'n_seeds':len(seeds),'settings':spec['settings'],'policies':spec['policies'],
        'thresholds':spec['taus'],'variants':spec['variants'],'base_config':base,'runs':len(rows),'elapsed_s':round(time.time()-start,1),'workers':workers,
        'python':platform.python_version(),'platform':platform.platform(),'cpus':os.cpu_count(),
        'source_sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        'warning':'Fresh synthetic results of the reconstruction plus a new predictor; not original project outcomes.'},indent=2))
    print(f'[{name}] wrote {len(rows)} runs to {out} in {time.time()-start:.0f}s; failures=0')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--suite',choices=['test','legacy','tau','robust','all'],default='test')
    p.add_argument('--config',default='configs/report_scale.json');p.add_argument('--output',default='results/improvement')
    p.add_argument('--workers',type=int,default=1);p.add_argument('--max-seeds',type=int,help='debug only: truncate seed lists')
    a=p.parse_args();c=json.loads(Path(a.config).read_text());specs=suites(c)
    for name in (['test','legacy','tau','robust'] if a.suite=='all' else [a.suite]):
        run_suite(name,specs[name],c,a.workers,a.max_seeds,Path(a.output)/name)
if __name__=='__main__':main()
