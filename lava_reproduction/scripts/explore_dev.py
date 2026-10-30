#!/usr/bin/env python3
"""Development-phase exploration on seeds 0-19 ONLY (kept for transparency).
Synthetic predictor: two rejected ideas, expected host-exit extension (*_ee) and MAP
lifetime class/confidence (*_map). Controlled predictor: the adopted *_bayes variants.
The prototype loop below mirrors lava.simulator; base policies are asserted identical."""
import sys,json,math,heapq,bisect,argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from lava.model import Predictor,trace,mixture_remaining
from lava.simulator import Host,deadline,simulate as reference,POLICIES,BAYES_POLICIES
from lava.stats import paired_diffs,t_test
C=json.loads((root/'configs/report_scale.json').read_text())
EXPLORE=['nilas_ee','lava_ee','lava_map','lava_map_ee','vm_ca_map','host_ca_map']
# Log-space Simpson grid (hours) for E[max(X,H)]-E[H] = integral of S_X(t) F_H(t) dt.
N=49;S0,S1=math.log(.005),math.log(3000.);HS=(S1-S0)/(N-1);T=[math.exp(S0+i*HS) for i in range(N)]
W=[(1 if i in (0,N-1) else 4 if i%2 else 2)*HS/3*T[i] for i in range(N)];W[0]+=T[0]/2;EXP={}
def survival(params,age):
    _,a,b=params;w=mixture_remaining(params,age)[1]
    ea=EXP.setdefault(a,[math.exp(-t/a) for t in T]);eb=EXP.setdefault(b,[math.exp(-t/b) for t in T])
    return [w*x+(1-w)*y for x,y in zip(ea,eb)]
def class_probs(c,params,age):
    _,a,b=params;w=mixture_remaining(params,age)[1];edges=[0]+c['class_bounds']+[math.inf]
    S=lambda t:0. if t==math.inf else w*math.exp(-t/a)+(1-w)*math.exp(-t/b)
    return [S(lo)-S(hi) for lo,hi in zip(edges,edges[1:])]

def simulate(records,c,seed,setting,policy,threshold=None):
    threshold=c['threshold'] if threshold is None else threshold
    base=policy.replace('_ee','').replace('_map','');ee=policy.endswith('_ee') and setting=='synthetic';use_map='_map' in policy and setting=='synthetic'
    pred=Predictor(c,seed,setting,records);hosts=[Host(i) for i in range(c['hosts'])];events=[]
    for r in records:heapq.heappush(events,(r.request.arrival,1,r.request.id,r.request))
    exits={r.request.id:r.request.arrival+r.duration for r in records}
    start=records[0].request.arrival;last=start;empty_area=0.;high=0
    while events:
        now,kind,vid,v=heapq.heappop(events);active=[h for h in hosts if h.vms];empty_area+=(now-last)*(len(hosts)-len(active));last=now
        if kind==0:
            h=v;request=h.vms.pop(vid);h.cpu-=request.cpu;h.mem-=request.mem;h.residual.discard(vid)
            if not h.vms:h.reset()
            elif h.state=='recycling' and not h.residual:h.cls=max(0,h.cls-1);h.residual=set(h.vms);h.deadline=deadline(c,h.cls,now)
            continue
        for h in active:
            while now>=h.deadline:h.cls=min(len(c['class_bounds']),h.cls+1);h.residual=set(h.vms);h.deadline=deadline(c,h.cls,h.deadline)
        remaining,confidence=pred.predict(v,now);k=pred.cls(remaining)
        if use_map:probs=class_probs(c,c['profiles'][v.profile],now-v.arrival);k=max(range(len(probs)),key=probs.__getitem__);confidence=probs[k]
        gate=confidence>=threshold;high+=gate
        mode='lava' if base not in ['best_fit','vm_ca','host_ca'] or (base in ['vm_ca','host_ca'] and gate) else 'baseline'
        feasible=[h for h in hosts if h.fits(v)]
        if base=='host_ca':feasible=[h for h in feasible if not h.vms or h.mode==mode] or feasible
        temporal={}
        if base in ['nilas','lava','vm_ca','host_ca'] and mode=='lava':
            sx=survival(c['profiles'][v.profile],now-v.arrival) if ee else None
            for h in feasible:
                if not ee:temporal[h.id]=max((pred.predict(x,now)[0] for x in h.vms.values()),default=0.);continue
                if not h.vms:temporal[h.id]=mixture_remaining(c['profiles'][v.profile],now-v.arrival)[0];continue
                F=[1.]*N
                for x in h.vms.values():F=[f*(1-s) for f,s in zip(F,survival(c['profiles'][x.profile],now-x.arrival))]
                temporal[h.id]=sum(w*a*f for w,a,f in zip(W,sx,F))
        def score(h):
            bf=(1-h.cpu-v.cpu)**2+(1-h.mem-v.mem)**2
            if mode=='baseline':return (bf,h.id)
            if base=='la_binary':return (0 if h.vms and h.binary==(remaining>=2) else 1 if h.vms else 2,bf,h.id)
            cost=bisect.bisect_left(c['temporal_bounds'],temporal[h.id] if ee else max(0,remaining-temporal[h.id]))
            if base=='nilas':return (cost,bf,h.id)
            rank,distance=(3,0) if not h.vms else (0,h.cls-k) if h.state=='recycling' and h.cls>k else (1,0) if h.state=='open' and h.cls==k else (2,0)
            return (rank,distance,cost,bf,h.id)
        h=min(feasible,key=score)
        if not h.vms:h.mode=mode;h.state='open';h.cls=k;h.binary=int(remaining>=2);h.deadline=deadline(c,k,now)
        h.vms[vid]=v;h.cpu+=v.cpu;h.mem+=v.mem
        if h.state=='open' and max(h.cpu,h.mem)>=c['recycle_at']:h.state='recycling';h.residual=set(h.vms)
        heapq.heappush(events,(exits[vid],0,vid,h))
    return dict(seed=seed,setting=setting,policy=policy,threshold=threshold,empty_pct=100*empty_area/(len(hosts)*(last-start)),high_gate=high,accepted=len(records),failures=0)

def job(a):
    seed,setting,policy,tau=a;records=trace(C,seed)
    r=(reference if policy in POLICIES+BAYES_POLICIES else simulate)(records,C,seed,setting,policy,tau)
    return dict(r,policy=policy+('' if tau is None else f'@{tau}'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--output',default='results/improvement/dev');a=p.parse_args()
    records=trace(C,0)
    for policy in POLICIES:
        assert simulate(records,C,0,'synthetic',policy)['empty_pct']==reference(records,C,0,'synthetic',policy)['empty_pct']
    seeds=range(20);tasks=[(s,'synthetic',x,None) for s in seeds for x in POLICIES+EXPLORE[:4]]
    tasks+=[(s,'synthetic',x,t) for s in seeds for x in EXPLORE[4:] for t in [.4,.5,.9]]
    tasks+=[(s,st,x,None) for s in seeds for st in ['0.25','0.5','0.75','0.85','1.0'] for x in POLICIES+BAYES_POLICIES]
    with ProcessPoolExecutor(a.workers) as pool:rows=list(pool.map(job,tasks,chunksize=4))
    summary=[]
    for setting in sorted({r['setting'] for r in rows}):
        for policy in dict.fromkeys(r['policy'] for r in rows if r['setting']==setting):
            for baseline in ['best_fit','lava']:
                if policy!=baseline:
                    mean,lo,hi,pv=t_test(paired_diffs(rows,policy,baseline,setting))
                    summary.append(dict(split='development seeds 0-19',setting=setting,policy=policy,baseline=baseline,mean=mean,low=lo,high=hi,p=pv))
    out=root/a.output;out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(summary,indent=2))
    for s in summary:print(f"{s['setting']:9s} {s['policy']:16s} vs {s['baseline']:8s} {s['mean']:+.3f} [{s['low']:+.3f}, {s['high']:+.3f}]")
if __name__=='__main__':main()
