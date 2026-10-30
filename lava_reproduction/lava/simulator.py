from __future__ import annotations

from dataclasses import dataclass,field
import heapq,bisect,math
from .model import Predictor,BayesPredictor
POLICIES=['best_fit','la_binary','nilas','lava','vm_ca','host_ca']
# Improvement: identical scheduling rules, prior-fused predictor (model.BayesPredictor).
BAYES_POLICIES=['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']

@dataclass
class Host:
    id:int
    cpu:float=0.
    mem:float=0.
    vms:dict=field(default_factory=dict)
    mode:str|None=None
    state:str='empty'
    cls:int=0
    deadline:float=math.inf
    residual:set=field(default_factory=set)
    binary:int=0
    def fits(self,v):return self.cpu+v.cpu<=1+1e-10 and self.mem+v.mem<=1+1e-10
    def reset(self):
        self.cpu=self.mem=0.; self.mode=None;self.state='empty';self.cls=0;self.deadline=math.inf;self.residual.clear()

def deadline(c,k,now):
    return now+(c['class_bounds']+[c['class_bounds'][-1]*10])[k]

def simulate(records,c,seed,setting,policy,threshold=None):
    assert policy in POLICIES+BAYES_POLICIES
    threshold=c['threshold'] if threshold is None else threshold
    base=policy[:-len('_bayes')] if policy in BAYES_POLICIES else policy
    pred=(BayesPredictor if base!=policy else Predictor)(c,seed,setting,records); hosts=[Host(i) for i in range(c['hosts'])]
    events=[]
    for r in records:
        heapq.heappush(events,(r.request.arrival,1,r.request.id,r.request))
    exits={r.request.id:r.request.arrival+r.duration for r in records}
    start=records[0].request.arrival if records else 0;last=start
    last_arrival=max((r.request.arrival for r in records),default=start);window_area=0.
    empty_area=packing_area=occupied_time=0.;accepted=failures=switches=cross_bl=cross_lb=fallback=high=0
    previous=None; max_cpu=max_mem=0.; steps=0
    while events:
        now,kind,vid,v=heapq.heappop(events); dt=now-last
        active=[h for h in hosts if h.vms]; occupied=len(active)
        empty_area+=dt*(len(hosts)-occupied)
        if now<=last_arrival:window_area+=dt*(len(hosts)-occupied)
        if occupied:
            packing_area+=dt*sum((h.cpu+h.mem)/2 for h in active)/occupied
            occupied_time+=dt
        last=now
        if kind==0:
            h=v;request=h.vms.pop(vid);h.cpu-=request.cpu;h.mem-=request.mem;h.residual.discard(vid)
            if not h.vms:h.reset()
            elif h.state=='recycling' and not h.residual:
                h.cls=max(0,h.cls-1);h.residual=set(h.vms);h.deadline=deadline(c,h.cls,now)
            continue
        # Lazy deadline processing is equivalent for placement; no occupancy changes.
        for h in active:
            while now>=h.deadline:
                h.cls=min(len(c['class_bounds']),h.cls+1);h.residual=set(h.vms)
                h.deadline=deadline(c,h.cls,h.deadline)
        remaining,confidence=pred.predict(v,now); k=pred.cls(remaining)
        gate=confidence>=threshold; high+=gate
        if previous is not None:switches+=gate!=previous
        previous=gate
        mode='lava' if base not in ['best_fit','vm_ca','host_ca'] or (base in ['vm_ca','host_ca'] and gate) else 'baseline'
        feasible=[h for h in hosts if h.fits(v)]
        if not feasible:failures+=1;continue
        if base=='host_ca':
            own=[h for h in feasible if not h.vms or h.mode==mode]
            if own:feasible=own
            else:fallback+=1
        # Re-predict each resident exactly once per arrival when temporal scoring is used.
        temporal={}
        if base in ['nilas','lava','vm_ca','host_ca'] and mode=='lava':
            for h in feasible:
                temporal[h.id]=max((pred.predict(x,now)[0] for x in h.vms.values()),default=0.)
        def score(h):
            bf=(1-h.cpu-v.cpu)**2+(1-h.mem-v.mem)**2
            if mode=='baseline':return (bf,h.id)
            if base=='la_binary':return (0 if h.vms and h.binary==(remaining>=2) else 1 if h.vms else 2,bf,h.id)
            cost=bisect.bisect_left(c['temporal_bounds'],max(0,remaining-temporal[h.id]))
            if base=='nilas':return (cost,bf,h.id)
            if not h.vms:rank=3;distance=0
            elif h.state=='recycling' and h.cls>k:rank=0;distance=h.cls-k
            elif h.state=='open' and h.cls==k:rank=1;distance=0
            else:rank=2;distance=0
            return (rank,distance,cost,bf,h.id)
        h=min(feasible,key=score)
        if h.vms and h.mode!=mode:
            if mode=='baseline':cross_bl+=1
            else:cross_lb+=1
        if not h.vms:
            h.mode=mode;h.state='open';h.cls=k;h.binary=int(remaining>=2);h.deadline=deadline(c,k,now)
        h.vms[vid]=v;h.cpu+=v.cpu;h.mem+=v.mem
        if h.state=='open' and max(h.cpu,h.mem)>=c['recycle_at']:
            h.state='recycling';h.residual=set(h.vms)
        max_cpu=max(max_cpu,h.cpu);max_mem=max(max_mem,h.mem)
        assert h.cpu<=1+1e-9 and h.mem<=1+1e-9
        accepted+=1;steps+=1
        heapq.heappush(events,(exits[vid],0,vid,h))
    horizon=last-start
    return dict(seed=seed,setting=setting,policy=policy,threshold=threshold,empty_pct=100*empty_area/(len(hosts)*horizon) if horizon else 100,packing_density=packing_area/occupied_time if occupied_time else 0,accepted=accepted,failures=failures,max_cpu=max_cpu,max_mem=max_mem,gate_switches=switches,high_gate=high,cross_baseline_into_lava=cross_bl,cross_lava_into_baseline=cross_lb,capacity_fallback=fallback,horizon=horizon,empty_pct_arrivals=100*window_area/(len(hosts)*(last_arrival-start)) if last_arrival>start else 100)
