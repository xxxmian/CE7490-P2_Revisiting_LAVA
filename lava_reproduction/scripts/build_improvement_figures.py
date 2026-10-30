#!/usr/bin/env python3
"""Figures for the prior-fusion improvement, from recorded NEW data only."""
from pathlib import Path
import sys,json,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lava.charts import plot
root=Path(__file__).resolve().parents[1]/'results/improvement'
out=root/'figures';out.mkdir(exist_ok=True)
load=lambda s:json.loads((root/s/'summary.json').read_text())
test,robust,tau=load('test'),load('robust'),load('tau')
def pick(rows,policy,baseline,setting,metric='empty_pct',**kw):
    return next(r for r in rows if r['policy']==policy and r['baseline']==baseline and r['setting']==setting and r['metric']==metric and all(r[k]==v for k,v in kw.items()))
ACC=['0.25','0.5','0.75','0.85','1.0']
curve=[pick(test,p,'best_fit',s) for s in ACC+['synthetic','oracle'] for p in ['lava','vm_ca','lava_bayes','vm_ca_bayes']]
plot(curve,out/'accuracy_curve.svg','IMPROVEMENT: vs Best-Fit, fresh seeds 1000-1099 (n=100), paired 95% CI')
family=[dict(r,setting=f"acc {r['setting']}, Holm p={r['p_holm']:.1e}") for r in test if r['primary']]
plot(family,out/'primary_family.svg','IMPROVEMENT: pre-registered family, seeds 1000-1099, paired 95% CI')
# Robustness seeds 2000-2049 only: same-seed protocol control, predictor variants, arrival rate x2.
# hosts=90 is omitted: it is a pure rescaling of the 180-host run (see IMPROVEMENT.md 6.6).
control,heavy=load('robust_control'),load('robust_load')
sel=lambda rows:[r for r in rows if r['policy']=='vm_ca_bayes' and r['baseline']=='lava' and r['metric']=='empty_pct' and r['variant']!='hosts=90']
rob=[dict(r,setting=f"{r['variant']} acc {r['setting']}") for r in sel(control)+sel(robust)+sel(heavy)]
plot(rob,out/'robustness.svg','IMPROVEMENT: VM-CA-Bayes minus LAVA, robustness seeds 2000-2049 (n=50), descriptive')
mech=[dict(pick(test,p,b,s,m),setting=f"{s} {'arrival window' if m=='empty_pct_arrivals' else 'full horizon'}")
      for p,b,s in [('host_ca','best_fit','synthetic'),('host_ca','vm_ca','synthetic'),('vm_ca_bayes','lava','0.25'),('vm_ca_bayes','lava','0.5')]
      for m in ['empty_pct_arrivals','empty_pct']]
plot(mech,out/'time_window.svg','DIAGNOSTIC: arrival window vs full horizon, seeds 1000-1099')
sens=[dict(r,setting=f"tau={r['threshold']} acc {r['setting']}") for r in tau if r['policy']=='vm_ca_bayes' and r['baseline']=='lava' and r['metric']=='empty_pct']
plot(sens,out/'tau_sensitivity.svg','SENSITIVITY: VM-CA-Bayes minus LAVA by threshold, validation seeds 200-219')

# Line chart for the report: improvement over Best-Fit vs controlled accuracy.
# Validated categorical slots 1-3 (light/dark); shapes are the secondary encoding.
SERIES=[('vm_ca_bayes','VM-CA-Bayes (proposed)','circle'),('lava_bayes','LAVA-Bayes (predictor only)','square'),('lava','LAVA (reconstruction)','diamond')]
def marker(shape,x,y,cls,tip):
    body={'circle':f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>','square':f'<rect x="{x-4:.1f}" y="{y-4:.1f}" width="8" height="8" rx="1"/>',
          'diamond':f'<path d="M{x:.1f} {y-5.5:.1f} L{x+5.5:.1f} {y:.1f} L{x:.1f} {y+5.5:.1f} L{x-5.5:.1f} {y:.1f} Z"/>'}[shape]
    return f'<g class="{cls} mark"><title>{tip}</title>{body}</g>'
def accuracy_chart(path):
    W,H,L,R,T,B=880,460,72,190,92,58;xs=[float(a) for a in ACC];oracle=pick(test,'lava','best_fit','oracle')
    vals=[v for p,_,_ in SERIES for a in ACC for v in (pick(test,p,'best_fit',a)['low'],pick(test,p,'best_fit',a)['high'])]+[0,oracle['mean']]
    lo,hi=min(vals),max(vals);step=.2;lo=step*math.floor(lo/step);hi=step*math.ceil(hi/step)
    X=lambda a:L+(W-L-R)*(a-.12)/(1.05-.12);Y=lambda v:T+(H-T-B)*(hi-v)/(hi-lo)
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="system-ui,-apple-system,Segoe UI,sans-serif">',
       '<style>svg{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a}'
       '@media (prefers-color-scheme:dark){svg{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70}}'
       '.l1{stroke:var(--s1)}.l2{stroke:var(--s2)}.l3{stroke:var(--s3)}.l1,.l2,.l3{fill:none}.m1{fill:var(--s1)}.m2{fill:var(--s2)}.m3{fill:var(--s3)}'
       '.mark>*:not(title){stroke:var(--surface);stroke-width:2}.mark:hover>*:not(title){stroke:var(--ink)}text{fill:var(--ink2);font-size:12px}</style>',
       '<rect width="100%" height="100%" fill="var(--surface)"/>',
       f'<text x="{L}" y="30" style="fill:var(--ink);font-size:16px;font-weight:600">Empty-host gain over Best-Fit vs prediction accuracy</text>',
       f'<text x="{L}" y="50">Fresh test seeds 1000-1099 (n=100). Paired mean, whiskers = 95% CI, percentage points.</text>']
    for i,(p,label,shape) in enumerate(SERIES):
        lx=L+i*235;s.append(marker(shape,lx+6,72,f'm{i+1}',label));s.append(f'<text x="{lx+18}" y="76" style="fill:var(--ink)">{label}</text>')
    v=lo
    while v<=hi+1e-9:
        s.append(f'<path d="M{L} {Y(v):.1f} H{W-R}" stroke="var(--{"axis" if abs(v)<1e-9 else "grid"})" stroke-width="1"/>')
        s.append(f'<text x="{L-10}" y="{Y(v)+4:.1f}" text-anchor="end" style="font-variant-numeric:tabular-nums">{v:+.1f}</text>');v+=step
    s.append(f'<text x="{W-R+8}" y="{Y(0)+4:.1f}" style="fill:var(--muted)">Best-Fit</text>')
    s.append(f'<path d="M{L} {Y(oracle["mean"]):.1f} H{W-R}" stroke="var(--muted)" stroke-width="1"/><text x="{W-R+8}" y="{Y(oracle["mean"])+4:.1f}" style="fill:var(--muted)">Oracle LAVA {oracle["mean"]:+.2f}</text>')
    for a in xs:s.append(f'<text x="{X(a):.1f}" y="{H-B+22}" text-anchor="middle">{a:.0%}</text>')
    s.append(f'<text x="{(L+W-R)/2:.0f}" y="{H-12}" text-anchor="middle">Controlled lifetime-prediction accuracy</text>')
    for i,(p,label,shape) in enumerate(SERIES):
        off=(i-1)*7;rows=[pick(test,p,'best_fit',a) for a in ACC]
        s.append(f'<path class="l{i+1}" d="'+' '.join(f'{"M" if j==0 else "L"}{X(x)+off:.1f} {Y(r["mean"]):.1f}' for j,(x,r) in enumerate(zip(xs,rows)))+'" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for x,r in zip(xs,rows):
            s.append(f'<path class="l{i+1}" d="M{X(x)+off:.1f} {Y(r["low"]):.1f} V{Y(r["high"]):.1f}" stroke-width="1.5" stroke-linecap="round"/>')
            s.append(marker(shape,X(x)+off,Y(r['mean']),f'm{i+1}',f'{label}, accuracy {x:.0%}: {r["mean"]:+.3f} pp [{r["low"]:+.3f}, {r["high"]:+.3f}]'))
        # Label only the separated 25% endpoints; VM-CA-Bayes sits on LAVA-Bayes (tooltip/table carry it).
        if p!='vm_ca_bayes':s.append(f'<text x="{X(xs[0])-16:.1f}" y="{Y(rows[0]["mean"])+4:.1f}" text-anchor="end">{rows[0]["mean"]:+.2f}</text>')
    s.append('</svg>');path.write_text('\n'.join(s))
accuracy_chart(out/'accuracy_line.svg')
print(out)
