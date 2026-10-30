"""Student-t intervals via incomplete beta; no optional packages required."""
import math,statistics

def betacf(a,b,x):
    qab=a+b;qap=a+1;qam=a-1;c=1.;d=1-qab*x/qap
    if abs(d)<1e-300:d=1e-300
    d=1/d;h=d
    for m in range(1,300):
        aa=m*(b-m)*x/((qam+2*m)*(a+2*m))
        d=1+aa*d;c=1+aa/c
        if abs(d)<1e-300:d=1e-300
        if abs(c)<1e-300:c=1e-300
        d=1/d;h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+2*m)*(qap+2*m))
        d=1+aa*d;c=1+aa/c
        if abs(d)<1e-300:d=1e-300
        if abs(c)<1e-300:c=1e-300
        d=1/d;delta=d*c;h*=delta
        if abs(delta-1)<3e-14:break
    return h

def ibeta(a,b,x):
    if x<=0:return 0.
    if x>=1:return 1.
    bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    if x<(a+1)/(a+b+2):return bt*betacf(a,b,x)/a
    return 1-bt*betacf(b,a,1-x)/b

def t_critical(df):
    lo,hi=0.,1e6
    for _ in range(90):
        mid=(lo+hi)/2
        cdf=1-.5*ibeta(df/2,.5,df/(df+mid*mid))
        if cdf<.975:lo=mid
        else:hi=mid
    return (lo+hi)/2

def interval(xs):
    n=len(xs)
    if n<2:raise ValueError('Paired CI requires at least two seeds')
    mean=statistics.mean(xs);half=t_critical(n-1)*statistics.stdev(xs)/math.sqrt(n)
    return mean,mean-half,mean+half

def paired_diffs(rows,policy,baseline,setting,metric='empty_pct'):
    a={r['seed']:r for r in rows if r['policy']==policy and r['setting']==setting}
    b={r['seed']:r for r in rows if r['policy']==baseline and r['setting']==setting}
    if not a or a.keys()!=b.keys():raise ValueError('Unpaired or missing seeds')
    for seed in a:
        if a[seed]['accepted']!=b[seed]['accepted'] or a[seed]['failures'] or b[seed]['failures']:
            raise ValueError('Admission mismatch/failures invalidate comparison')
    return [a[s][metric]-b[s][metric] for s in sorted(a)]

def paired(rows,policy,baseline,setting):return interval(paired_diffs(rows,policy,baseline,setting))

def t_test(xs):
    """Mean, 95% CI and two-sided one-sample (paired) Student-t p-value."""
    mean,lo,hi=interval(xs);sd=statistics.stdev(xs);df=len(xs)-1
    if sd==0:return mean,lo,hi,(1. if mean==0 else 0.)
    t=mean/(sd/math.sqrt(len(xs)))
    return mean,lo,hi,ibeta(df/2,.5,df/(df+t*t))

def holm(ps):
    """Holm-Bonferroni adjusted p-values, same order as input."""
    order=sorted(range(len(ps)),key=ps.__getitem__);adj=[0.]*len(ps);run=0.
    for rank,i in enumerate(order):run=max(run,min(1.,(len(ps)-rank)*ps[i]));adj[i]=run
    return adj
