"""Workload truth is separate from scheduler-visible requests/predictions. Hours throughout."""
from dataclasses import dataclass
import random, math, bisect

@dataclass(frozen=True)
class Request:
    id:int
    arrival:float
    cpu:float
    mem:float
    profile:str

@dataclass(frozen=True)
class Record:
    request:Request
    duration:float

def trace(config,seed):
    rng=random.Random(seed); t=0; out=[]
    names=list(config['profiles'])
    for i in range(config['vms']):
        t+=rng.expovariate(config['arrival_rate'])
        name=rng.choices(names,config['profile_weights'])[0]
        p,a,b=config['profiles'][name]
        duration=max(1e-8,rng.expovariate(1/(a if rng.random()<p else b)))
        cpu,mem=rng.choices(config['shapes'],config['shape_weights'])[0]
        out.append(Record(Request(i,t,cpu,mem,name),duration))
    return out

def mixture_remaining(params,uptime):
    p,a,b=params
    # Log-sum-exp avoids survival underflow for very old VMs.
    x=math.log(p)-uptime/a; y=math.log1p(-p)-uptime/b
    m=max(x,y); w=math.exp(x-m)/(math.exp(x-m)+math.exp(y-m))
    return w*a+(1-w)*b,w

def normal_cdf(x):return .5*math.erfc(-x/math.sqrt(2))

def profile_prediction(c,params,age):
    """Conditional mean remaining lifetime (capped) and mass of its class interval."""
    mean,w=mixture_remaining(params,age)
    mean=min(mean,c['cap_hours']); k=bisect.bisect_right(c['class_bounds'],mean)
    lo=0 if k==0 else c['class_bounds'][k-1]
    hi=math.inf if k==len(c['class_bounds']) else c['class_bounds'][k]
    _,a,b=params
    confidence=w*(math.exp(-lo/a)-math.exp(-hi/a))+(1-w)*(math.exp(-lo/b)-math.exp(-hi/b))
    return mean,confidence

class Predictor:
    def __init__(self,config,seed,setting,records):
        self.c=config; self.setting=setting; self.values={}
        good,bad=config.get('noise_sigmas',[.001,3.])
        # Only this experimental harness has truth. Scheduler never receives records.
        rng=random.Random(seed+10_000_019)
        for record in records:
            if setting=='oracle': self.values[record.request.id]=record.duration
            elif setting!='synthetic':
                accuracy=float(setting)
                sigma=good if rng.random()<accuracy else bad
                self.values[record.request.id]=min(config['cap_hours'],max(1e-8,record.duration*10**max(-100,min(100,rng.gauss(0,sigma)))))
    def cls(self,r):return bisect.bisect_right(self.c['class_bounds'],r)
    def predict(self,request,now):
        age=max(0,now-request.arrival)
        if self.setting=='synthetic':return profile_prediction(self.c,self.c['profiles'][request.profile],age)
        observed=self.values[request.id]
        if self.setting=='oracle':return max(1e-8,observed-age),1.
        # Inferred log-uniform prior for total lifetime: posterior log(T) is
        # calibrated mixture around log(observed), conditioned on survival T>age.
        # Uses global accuracy only, NEVER the sampled bucket or true lifetime.
        acc=float(self.setting); center=math.log10(observed); good,bad=self.c.get('noise_sigmas',[.001,3.])
        def cdf(t,s):return 0. if t<=0 else (1. if math.isinf(t) else normal_cdf((math.log10(t)-center)/s))
        def mass(lo,hi):return sum(w*(cdf(hi,s)-cdf(lo,s)) for w,s in [(acc,good),(1-acc,bad)])
        r=max(1e-8,observed-age) if observed>age else min(self.c['cap_hours'],max(.1,age))
        k=self.cls(r); lo=0 if k==0 else self.c['class_bounds'][k-1]
        hi=math.inf if k==len(self.c['class_bounds']) else self.c['class_bounds'][k]
        return r,min(1.,mass(age+lo,age+hi)/max(1e-300,mass(age,math.inf)))

GRID_DECADES=(-4.,4.5); GRID_PER_DECADE=50; NARROW_Z=range(-4,5)

class BayesPredictor(Predictor):
    """Improvement: fuse the noisy controlled value with the profile prior (the
    synthetic model). Same scheduler-visible information as Predictor: noisy value,
    global accuracy, error sigmas and cap; NEVER the sampled bucket or true lifetime.
    Posterior over total lifetime is a set of weighted atoms on a log10 grid plus the
    narrow-error component; uptime conditioning keeps atoms above the current age.
    A value at the cap is treated as censored, P(noisy value >= cap | T)."""
    def __init__(self,config,seed,setting,records):
        super().__init__(config,seed,setting,records)
        self.prior=config.get('prior_profiles',config['profiles']); self.post={}
        self.sigmas=config.get('fusion_sigmas',config.get('noise_sigmas',[.001,3.]))
        n=int(round((GRID_DECADES[1]-GRID_DECADES[0])*GRID_PER_DECADE))
        self.x=[GRID_DECADES[0]+(j+.5)/GRID_PER_DECADE for j in range(n)]; self.t=[10**x for x in self.x]
        edges=[10**(GRID_DECADES[0]+j/GRID_PER_DECADE) for j in range(1,n)]; self.cells={}
        for name,(p,a,b) in self.prior.items():
            cdf=[0.]+[1-p*math.exp(-t/a)-(1-p)*math.exp(-t/b) for t in edges]+[1.]
            self.cells[name]=[max(0.,hi-lo) for lo,hi in zip(cdf,cdf[1:])]
        z=[math.exp(-k*k/2) for k in NARROW_Z]; self.narrow=[v/sum(z) for v in z]
    def posterior(self,request):
        acc=float(self.setting); o=self.values[request.id]; good,bad=self.sigmas; cap=self.c['cap_hours']
        p,a,b=self.prior[request.profile]; cells=self.cells[request.profile]
        if o>=cap:
            lc=math.log10(cap)
            atoms=[(t,m*(acc*normal_cdf((x-lc)/good)+(1-acc)*normal_cdf((x-lc)/bad))) for x,t,m in zip(self.x,self.t,cells)]
        else:
            lo=math.log10(o); norm=1/(bad*math.sqrt(2*math.pi))
            atoms=[(t,m*(1-acc)*norm*math.exp(-.5*((lo-x)/bad)**2)) for x,t,m in zip(self.x,self.t,cells)]
            # Narrow component: likelihood width << grid, so weight = prior density of log10 T at o.
            density=(p/a*math.exp(-o/a)+(1-p)/b*math.exp(-o/b))*o*math.log(10)
            atoms+=[(10**(lo+good*k),acc*density*v) for k,v in zip(NARROW_Z,self.narrow)]
        atoms=sorted(x for x in atoms if x[1]>0); T=[t for t,_ in atoms]
        mass=[0.]*(len(T)+1); first=[0.]*(len(T)+1)
        for i in range(len(T)-1,-1,-1):mass[i]=mass[i+1]+atoms[i][1];first[i]=first[i+1]+atoms[i][1]*T[i]
        return T,mass,first
    def predict(self,request,now):
        if self.setting in ('synthetic','oracle'):return super().predict(request,now)
        if request.id not in self.post:self.post[request.id]=self.posterior(request)
        T,mass,first=self.post[request.id]; age=max(0,now-request.arrival); i=bisect.bisect_right(T,age)
        if mass[i]<=1e-300:return profile_prediction(self.c,self.prior[request.profile],age)
        r=min(self.c['cap_hours'],max(1e-8,first[i]/mass[i]-age)); k=self.cls(r)
        lo=0 if k==0 else self.c['class_bounds'][k-1]
        hi=math.inf if k==len(self.c['class_bounds']) else self.c['class_bounds'][k]
        inside=mass[bisect.bisect_left(T,age+lo)]-(0. if math.isinf(hi) else mass[bisect.bisect_left(T,age+hi)])
        return r,min(1.,max(0.,inside/mass[i]))
